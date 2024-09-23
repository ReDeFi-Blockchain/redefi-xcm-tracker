from flask import Flask, send_from_directory, render_template, request
import polkascan
import pymysql
import os
from envs import DEBUG, HOST, PORT

app = Flask(__name__)

@app.before_request
def before_request():
    if request.path == '/' or request.path.startswith('/0x'):
        polkascan.setup_connections()

@app.teardown_request
def teardown_request(e):
    if request.path == '/' or request.path.startswith('/0x'):
        polkascan.close_connections()

@app.errorhandler(pymysql.Error)
def handle_exception(e):
    app.logger.error(f'MySQL error: {e}')
    return render_template('error.html', input=request.path[1:], error='Internal error')

@app.errorhandler(Exception)
def handle_exception(e):
    return render_template('error.html', input=request.path[1:], error=str(e))

@app.route('/favicon.ico')
def favicon():
    return send_from_directory(
        directory=os.path.join(app.root_path, 'static'),
        path='favicon.ico',
        mimetype='image/vnd.microsoft.icon')

@app.route('/')
@app.route('/<tx_hash>')
def view(tx_hash=None):
    if tx_hash:
        return render_template('status.html', input=tx_hash, tx=polkascan.get_transaction(tx_hash))
    else:
        return render_template('base.html')

if __name__ == "__main__":
    print(f'Listening {HOST}:{PORT}')

    if DEBUG:
        app.run(host=HOST, port=PORT, debug=True, load_dotenv=False)
    else:
        from waitress import serve
        serve(app, host=HOST, port=PORT)
