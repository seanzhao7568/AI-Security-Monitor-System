from flask import Flask
from monitor.core import SecurityMonitor
from web.routes import register_routes

app = Flask(__name__)
monitor = SecurityMonitor()
register_routes(app, monitor)

if __name__ == "__main__":
    print("啟動中：http://127.0.0.1:5000")
    app.run(host="0.0.0.0", port=5000, debug=False, threaded=True)
