"""Core code generation using LLMs.

Orchestrates the generation loop: prompt → LLM → extract code → post-process.
"""

from __future__ import annotations

import os
import time
from typing import TYPE_CHECKING

import structlog

from axiom._generated import extract_code
from axiom.codegen.prompt_builder import (
    build_retry_prompt,
    build_system_prompt,
    build_user_prompt,
)
from axiom.errors import APIError, GenerationError

if TYPE_CHECKING:
    from axiom.config.settings import Settings
    from axiom.spec.models import Spec

logger = structlog.get_logger()


class GenerationResult:
    """Result of code generation.

    Attributes:
        code: The generated Python code.
        model: The model used for generation.
        attempts: Number of attempts made.
        duration_ms: Total generation time in milliseconds.
    """

    def __init__(
        self,
        code: str,
        model: str,
        attempts: int,
        duration_ms: int,
    ) -> None:
        self.code = code
        self.model = model
        self.attempts = attempts
        self.duration_ms = duration_ms


def generate_code(
    spec: Spec,
    settings: Settings,
    model_override: str | None = None,
) -> GenerationResult:
    """Generate code from a spec.

    Args:
        spec: The parsed spec.
        settings: Axiom settings.
        model_override: Optional model to use instead of settings default.

    Returns:
        GenerationResult with the generated code.

    Raises:
        GenerationError: If generation fails after all retries.
        APIError: If the LLM API call fails.
    """
    model = model_override or settings.get_model_for_target(spec.metadata.target)
    max_retries = settings.generation.max_retries

    logger.info(
        "Starting code generation",
        spec=spec.spec_name,
        model=model,
        max_retries=max_retries,
    )

    start_time = time.time()
    failures: list[str] = []

    for attempt in range(1, max_retries + 1):
        logger.debug("Generation attempt", attempt=attempt, spec=spec.spec_name)

        try:
            # Build prompt
            if attempt == 1:
                user_prompt = build_user_prompt(spec)
            else:
                user_prompt = build_retry_prompt(spec, failures)

            system_prompt = build_system_prompt(spec.metadata.target)

            # Call LLM
            raw_response = _call_llm(
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                model=model,
                temperature=settings.generation.temperature,
                timeout=settings.generation.timeout_seconds,
            )

            # Extract and clean code
            code = extract_code(raw_response)

            duration_ms = int((time.time() - start_time) * 1000)

            logger.info(
                "Generation succeeded",
                spec=spec.spec_name,
                attempt=attempt,
                duration_ms=duration_ms,
            )

            return GenerationResult(
                code=code,
                model=model,
                attempts=attempt,
                duration_ms=duration_ms,
            )

        except APIError:
            # Re-raise API errors - they should be handled by caller
            raise
        except Exception as e:
            failure_msg = f"Attempt {attempt}: {e}"
            failures.append(failure_msg)
            logger.warning(
                "Generation attempt failed",
                attempt=attempt,
                error=str(e),
                spec=spec.spec_name,
            )

            if attempt == max_retries:
                raise GenerationError(
                    f"All {max_retries} generation attempts failed. "
                    f"Last error: {e}. "
                    "Consider simplifying the spec or adding more examples.",
                    spec_name=spec.spec_name,
                    attempt=attempt,
                ) from e

    # Should never reach here
    raise GenerationError(
        "Generation failed unexpectedly",
        spec_name=spec.spec_name,
    )


def generate_with_verification(
    spec: Spec,
    settings: Settings,
    verify_fn: object,  # Callable that returns (success, failures)
    model_override: str | None = None,
) -> GenerationResult:
    """Generate code with verification in the loop.

    Retries generation if verification fails, incorporating failure information.

    Args:
        spec: The parsed spec.
        settings: Axiom settings.
        verify_fn: Function that takes code and returns (success: bool, failures: list[str]).
        model_override: Optional model to use.

    Returns:
        GenerationResult with verified code.

    Raises:
        GenerationError: If generation + verification fails after all retries.
    """
    model = model_override or settings.get_model_for_target(spec.metadata.target)
    max_retries = settings.generation.max_retries

    logger.info(
        "Starting generation with verification",
        spec=spec.spec_name,
        model=model,
    )

    start_time = time.time()
    all_failures: list[str] = []

    for attempt in range(1, max_retries + 1):
        # Build prompt
        if attempt == 1:
            user_prompt = build_user_prompt(spec)
        else:
            user_prompt = build_retry_prompt(spec, all_failures)

        system_prompt = build_system_prompt(spec.metadata.target)

        try:
            # Generate
            raw_response = _call_llm(
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                model=model,
                temperature=settings.generation.temperature,
                timeout=settings.generation.timeout_seconds,
            )

            code = extract_code(raw_response)

            # Verify
            success, failures = verify_fn(code)  # type: ignore[operator]

            if success:
                duration_ms = int((time.time() - start_time) * 1000)
                logger.info(
                    "Generation + verification succeeded",
                    spec=spec.spec_name,
                    attempt=attempt,
                    duration_ms=duration_ms,
                )
                return GenerationResult(
                    code=code,
                    model=model,
                    attempts=attempt,
                    duration_ms=duration_ms,
                )

            # Verification failed
            all_failures.extend(failures)
            logger.warning(
                "Verification failed, retrying",
                attempt=attempt,
                failures=failures,
                spec=spec.spec_name,
            )

        except APIError:
            raise
        except Exception as e:
            all_failures.append(f"Attempt {attempt}: {e}")
            logger.warning(
                "Generation attempt failed",
                attempt=attempt,
                error=str(e),
            )

    # All attempts exhausted
    raise GenerationError(
        f"Generation failed verification after {max_retries} attempts. "
        f"Failures: {'; '.join(all_failures[-3:])}",  # Last 3 failures
        spec_name=spec.spec_name,
        attempt=max_retries,
    )


def _call_llm(
    system_prompt: str,
    user_prompt: str,
    model: str,
    temperature: float,
    timeout: int,
) -> str:
    """Call the LLM API.

    Args:
        system_prompt: The system prompt.
        user_prompt: The user prompt.
        model: Model name.
        temperature: Generation temperature.
        timeout: Request timeout in seconds.

    Returns:
        The raw response text.

    Raises:
        APIError: If the API call fails.
    """
    # Check for API key
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        raise APIError(
            "ANTHROPIC_API_KEY environment variable not set. "
            "Set it with: export ANTHROPIC_API_KEY=your-key",
            provider="anthropic",
            retryable=False,
        )

    try:
        import anthropic

        client = anthropic.Anthropic(api_key=api_key, timeout=timeout)

        message = client.messages.create(
            model=model,
            max_tokens=4096,
            temperature=temperature,
            system=system_prompt,
            messages=[{"role": "user", "content": user_prompt}],
        )

        # Extract text from response
        if message.content and len(message.content) > 0:
            content = message.content[0]
            if hasattr(content, "text"):
                return content.text

        raise APIError(
            "Empty response from API",
            provider="anthropic",
            retryable=True,
        )

    except anthropic.APIStatusError as e:
        retryable = e.status_code in (429, 500, 502, 503, 504)
        raise APIError(
            str(e.message),
            provider="anthropic",
            status_code=e.status_code,
            retryable=retryable,
        ) from e
    except anthropic.APIConnectionError as e:
        raise APIError(
            f"Connection error: {e}",
            provider="anthropic",
            retryable=True,
        ) from e
    except Exception as e:
        raise APIError(
            f"Unexpected error: {e}",
            provider="anthropic",
            retryable=False,
        ) from e
