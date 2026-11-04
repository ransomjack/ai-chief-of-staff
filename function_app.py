"""Azure Functions entry points.

1. whatsapp_webhook  Meta calls this for every message. It checks Meta's signature,
                     drops anything not from the owner, queues the message and answers
                     200 at once (Meta retries if it waits too long).
2. process_inbound   Picks messages off the queue, runs Claude and replies.
3. reminder_tick     Every 5 minutes: sends reminders that are due.
4. morning_brief     09:00 IST every day (03:30 UTC).
"""
import json
import logging

import azure.functions as func

from cos.jobs import handle_inbound, run_morning, run_reminders
from cos.whatsapp import Inbound, parse_webhook, verify_signature
from cos.wiring import deps, settings

app = func.FunctionApp(http_auth_level=func.AuthLevel.ANONYMOUS)


@app.route(route="whatsapp", methods=["GET", "POST"])
@app.queue_output(arg_name="out", queue_name="inbound", connection="AzureWebJobsStorage")
def whatsapp_webhook(req: func.HttpRequest, out: func.Out[str]) -> func.HttpResponse:
    s = settings()
    if req.method == "GET":  # one-time handshake when the webhook is registered in Meta
        if req.params.get("hub.mode") == "subscribe" and req.params.get("hub.verify_token") == s.wa_verify_token:
            return func.HttpResponse(req.params.get("hub.challenge", ""), status_code=200)
        return func.HttpResponse("forbidden", status_code=403)

    raw = req.get_body()
    if not verify_signature(raw, req.headers.get("X-Hub-Signature-256"), s.wa_app_secret):
        logging.warning("Rejected webhook with a bad or missing signature")
        return func.HttpResponse("bad signature", status_code=401)
    try:
        items = parse_webhook(json.loads(raw))
    except ValueError:
        return func.HttpResponse("bad json", status_code=400)
    mine = [i.to_dict() for i in items if i.sender == s.owner_number]
    if mine:  # one queue message holding a list; process_inbound handles each item
        out.set(json.dumps(mine))
    return func.HttpResponse("ok", status_code=200)


@app.queue_trigger(arg_name="msg", queue_name="inbound", connection="AzureWebJobsStorage")
def process_inbound(msg: func.QueueMessage) -> None:
    data = json.loads(msg.get_body().decode())
    for item in data if isinstance(data, list) else [data]:
        handle_inbound(Inbound(**item), deps())


@app.timer_trigger(arg_name="timer", schedule="0 */5 * * * *", run_on_startup=False)
def reminder_tick(timer: func.TimerRequest) -> None:
    sent = run_reminders(deps())
    if sent:
        logging.info("Sent reminders: %s", ", ".join(sent))


@app.timer_trigger(arg_name="timer", schedule="0 30 3 * * *", run_on_startup=False)
def morning_brief(timer: func.TimerRequest) -> None:
    logging.info("Morning: sent %s", run_morning(deps()))
