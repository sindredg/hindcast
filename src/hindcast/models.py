"""Model calls through the Foundry project, signed in with Entra ID, no keys.

Every call goes to the project endpoint, so the Foundry User role at project
scope is enough. The resource endpoint (Content Understanding) authorises at
resource scope and needs its own role.
"""

import base64
import functools

from azure.ai.projects import AIProjectClient
from azure.identity import DefaultAzureCredential
from openai import OpenAI

from hindcast.config import ModelSettings, load_settings
from hindcast.costs import TokenUsage

# Image types the Responses API accepts here, told apart by their first bytes.
IMAGE_TYPES = {b"\x89PNG": "image/png", b"\xff\xd8\xff": "image/jpeg"}


@functools.cache
def project_client() -> AIProjectClient:
    # DefaultAzureCredential finds the az or azd sign-in locally and the managed
    # identity in Azure. Cached so the process signs in once.
    return AIProjectClient(
        endpoint=load_settings(ModelSettings).project_endpoint, credential=DefaultAzureCredential()
    )


@functools.cache
def openai_client() -> OpenAI:
    # An openai.OpenAI client pointed at the project and carrying the same
    # credential. It retries 429 and 5xx twice with backoff by default.
    return project_client().get_openai_client()


def _image_part(image: bytes) -> dict:
    mime = next((t for magic, t in IMAGE_TYPES.items() if image.startswith(magic)), None)
    if mime is None:
        raise ValueError("image must be PNG or JPEG")
    data = base64.b64encode(image).decode("ascii")
    return {"type": "input_image", "image_url": f"data:{mime};base64,{data}"}


def ask_model(
    deployment: str,
    system: str,
    user: str,
    *,
    image: bytes | None = None,
    effort: str = "medium",
) -> tuple[str, TokenUsage]:
    """One Responses API call: system prompt as instructions, one user turn, optional image."""
    content: list[dict] = [{"type": "input_text", "text": user}]
    if image is not None:
        content.append(_image_part(image))

    # Reasoning effort is sent even when it equals the service default (medium),
    # so a change of that default cannot change results silently. No temperature
    # or top_p: the gpt-6 models reject top_p on the Responses API.
    response = openai_client().responses.create(
        model=deployment,
        instructions=system,
        input=[{"role": "user", "content": content}],
        reasoning={"effort": effort},
    )

    if response.status != "completed":
        # A cut answer (output limit, content filter) still carries text.
        reason = getattr(response.incomplete_details, "reason", None)
        raise RuntimeError(f"{deployment} answer is {response.status}: {reason}")

    text = response.output_text
    if not text or not text.strip():
        # An empty answer must fail loudly, never pass as a result.
        raise RuntimeError(f"{deployment} returned an empty answer")

    usage = response.usage
    # Reasoning tokens are billed as output and are already in output_tokens.
    details = usage.input_tokens_details
    return text, TokenUsage(
        input_tokens=usage.input_tokens,
        cached_input_tokens=details.cached_tokens if details else 0,
        output_tokens=usage.output_tokens,
    )


def deployment_model(deployment: str) -> tuple[str, str]:
    """(model name, model version) of a deployment; the response's model field has no version."""
    deployed = project_client().deployments.get(deployment)
    if not deployed.model_name or not deployed.model_version:
        raise RuntimeError(f"deployment {deployment} reports no model name or version")
    return deployed.model_name, deployed.model_version
