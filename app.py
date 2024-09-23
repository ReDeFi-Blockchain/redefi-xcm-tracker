from flask import Flask, send_from_directory, render_template
from polkascan import get_transaction
import pymysql
import os
from envs import DEBUG, HOST, PORT

app = Flask(__name__)

@app.route('/favicon.ico')
def favicon():
    return send_from_directory(os.path.join(app.root_path, 'static'),
                               'favicon.ico', mimetype='image/vnd.microsoft.icon')

@app.route('/')
@app.route('/<tx_hash>')
def hello(tx_hash=None):
    if not tx_hash:
        return render_template('base.html')
    
    try:
        return render_template('status.html', input=tx_hash, tx=get_transaction(tx_hash))
    except pymysql.Error as e:
        app.logger.error(f'MySQL error: {e}')
        return render_template('error.html', input=tx_hash, error='internal error')
    except Exception as e:
        return render_template('error.html', input=tx_hash, error=str(e))

if __name__ == "__main__":
    print(f'Listening {HOST}:{PORT}')
    
    if DEBUG:
        app.run(host=HOST, port=PORT, debug=True, load_dotenv=False)
    else:
        from waitress import serve
        serve(app, host=HOST, port=PORT)
