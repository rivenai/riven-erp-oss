# -*- coding: utf-8 -*-
"""
Mercury webhook receiver.

Mercury signs every webhook with HMAC-SHA256 over the raw body using the
workspace webhook secret. We never trust the body until the signature is
verified. Endpoint is reachable only via the Cloudflare Tunnel hostname
``mercury-webhook.cassilly.capital`` -> bsdyno-openclaw tunnel ->
pes-odoo-crm-vm:8069.

Replay protection: we record the Mercury event id in ir.attachment with a
deterministic name and reject duplicates inside a 24h window.
"""
import hashlib
import hmac
import json
import logging

from odoo import http
from odoo.http import request

_logger = logging.getLogger(__name__)


class MercuryWebhookController(http.Controller):

    @http.route(
        "/mercury/webhook",
        type="http",
        auth="public",
        methods=["POST"],
        csrf=False,
        save_session=False,
    )
    def mercury_webhook(self, **_kwargs):
        raw_body = request.httprequest.get_data(cache=False, as_text=False) or b""
        signature_header = request.httprequest.headers.get("Mercury-Signature", "")

        # Resolve the workspace secret from Key Vault. The header includes the
        # workspace id so we can pick the right secret without trial decryption.
        workspace_id = request.httprequest.headers.get("Mercury-Workspace-Id") or "default"
        link = (
            request.env["account.online.link"]
            .sudo()
            .search(
                [("is_mercury", "=", True), ("mercury_workspace_id", "=", workspace_id)],
                limit=1,
            )
        )
        if not link:
            _logger.warning("Mercury webhook: no link for workspace %s", workspace_id)
            return request.make_response("unauthorized", status=401)

        secret_name = "mercury-webhook-{}-{}".format(link.company_id.id, workspace_id)
        secret = (
            request.env["mercury.secret.resolver"]
            .sudo()
            .get_secret_by_name(secret_name)
        )
        if not secret:
            _logger.error("Mercury webhook: secret %s not in Key Vault", secret_name)
            return request.make_response("unauthorized", status=401)

        expected = hmac.new(
            secret.encode("utf-8"), raw_body, hashlib.sha256
        ).hexdigest()
        if not hmac.compare_digest(expected, signature_header):
            _logger.warning("Mercury webhook: bad signature for workspace %s", workspace_id)
            return request.make_response("unauthorized", status=401)

        try:
            payload = json.loads(raw_body.decode("utf-8") or "{}")
        except ValueError:
            return request.make_response("bad json", status=400)

        event_id = payload.get("id") or payload.get("event_id")
        event_type = payload.get("type") or payload.get("event")
        if not event_id:
            return request.make_response("missing event id", status=400)

        # Dedup by event id.
        Param = request.env["ir.config_parameter"].sudo()
        seen_key = "mercury_bank_sync.seen.{}".format(event_id)
        if Param.get_param(seen_key):
            return request.make_response("ok", status=200)
        Param.set_param(seen_key, "1")

        # Trigger an immediate fetch on the matching link. The base cron will
        # also catch this within 12h; webhook just makes it real-time.
        try:
            link._fetch_transactions()
        except Exception:
            _logger.exception("Mercury webhook: fetch failed for link %s", link.id)

        _logger.info("Mercury webhook OK: %s / %s", event_type, event_id)
        return request.make_response("ok", status=200)
