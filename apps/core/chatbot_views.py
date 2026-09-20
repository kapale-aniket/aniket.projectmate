"""Public ProjectMateBot chat API — knowledge-base answers only."""
import json

from django.http import JsonResponse
from django.views.decorators.http import require_POST

from apps.core.chatbot_service import ask_matebot


def _json_body(request):
    try:
        return json.loads(request.body.decode("utf-8") or "{}")
    except json.JSONDecodeError:
        return {}


@require_POST
def chatbot_ask(request):
    body = _json_body(request)
    message = (body.get("message") or body.get("q") or "").strip()
    history = body.get("history") or []

    if not message:
        return JsonResponse(
            {"ok": False, "reply": "Please type a message.", "mode": "kb", "matched": False},
            status=400,
        )

    if len(message) > 4000:
        return JsonResponse(
            {
                "ok": False,
                "reply": "Message is too long. Please shorten it.",
                "mode": "kb",
                "matched": False,
            },
            status=400,
        )

    if not isinstance(history, list):
        history = []
    if len(history) > 20:
        history = history[-20:]

    result = ask_matebot(message, history)
    return JsonResponse(
        {
            "ok": True,
            "reply": result.get("reply", ""),
            "mode": "kb",
            "matched": bool(result.get("matched")),
            "ai_enabled": False,
            "understood": result.get("understood", ""),
        }
    )
