import time
from flask import Response, jsonify, request, render_template_string
from web.templates import INDEX_HTML


def register_routes(app, monitor):
    @app.route("/")
    def index():
        return render_template_string(INDEX_HTML)

    @app.route("/api/status")
    def api_status():
        return jsonify(monitor.get_status())

    @app.route("/start", methods=["POST"])
    def start_monitor():
        monitor.start()
        return jsonify({"ok": True, "message": "監控已開始"})

    @app.route("/stop", methods=["POST"])
    def stop_monitor():
        monitor.stop()
        return jsonify({"ok": True, "message": "監控已停止"})

    @app.route("/api/config/telegram", methods=["POST"])
    def save_telegram():
        data = request.get_json(silent=True) or {}
        token = data.get("token", "")
        chat_id = data.get("chat_id", "")
        monitor.update_telegram(token, chat_id)
        return jsonify({"ok": True, "message": "Telegram 設定已更新"})

    @app.route("/api/config/toggles", methods=["POST"])
    def save_toggles():
        data = request.get_json(silent=True) or {}
        monitor.update_toggles(data)
        return jsonify({"ok": True, "message": "功能開關已更新"})

    @app.route("/api/test_telegram", methods=["POST"])
    def api_test_telegram():
        ok, message = monitor.test_telegram()
        return jsonify({"ok": ok, "message": message})

    @app.route("/video_feed")
    def video_feed():
        def gen():
            while True:
                jpg = monitor.get_jpeg()
                if jpg is None:
                    time.sleep(0.05)
                    continue
                yield (b"--frame\r\n" b"Content-Type: image/jpeg\r\n\r\n" + jpg + b"\r\n")
                time.sleep(0.03)
        return Response(gen(), mimetype="multipart/x-mixed-replace; boundary=frame")
