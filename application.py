import json
import os
import os.path
from datetime import date, timedelta
from os import path

from flask import Flask, Response, jsonify, render_template, request
from werkzeug.exceptions import HTTPException

from dicttoxml import dicttoxml
from folioclient.FolioClient import FolioClient
from lxml import etree

app = Flask(__name__)


def get_file_path():
    path_debug = os.environ.get('DATA_FOLDER_PATH', '/MADE_UP')
    path_real = '/home'
    if os.path.exists(path_debug):
        return os.path.join(path_debug, 'stats.json')
    if os.path.exists(path_real):
        return os.path.join(path_real, 'stats.json')
    raise Exception('None of the paths exists')


@app.route('/rtac', methods=['GET'])
def rtac():
    folio_client = FolioClient(
        os.environ['OKAPI_URL'],
        os.environ['TENANT_ID'],
        os.environ['FOLIO_USERNAME'],
        os.environ['FOLIO_PASSWORD'])
    bib_id = request.args.get('Bib_ID')
    onr = request.args.get('ONR')
    issn = request.args.get('ISSN')
    isbn = request.args.get('ISBN')
    resp = create_rtac_response(folio_client, bib_id)
    if bib_id:
        root = etree.Element('Item_Information')
        for itemd in resp:
            item = etree.fromstring(itemd)
            root.append(item)
        return Response(etree.tostring(root), mimetype='text/xml')
    else:
        raise ValueError(
            'bib id missing. other identifiers not yet implemented')


@app.route('/')
def hello_world():
    return "RTAC  and statistics app from FOLIO"


@app.route('/statistics/')
@app.route('/statistics/<date>')
def hi(date=date.today()):
    definitions = list()
    with open('stats_definitions.json') as jf:
        definitions = json.load(jf)
    names = list([f['name'] for f in definitions])
    names.sort()
    return render_template('stats_main.html',
                           date=date,
                           measures=names,
                           seven_days_back=date.today() - timedelta(days=7),
                           thirty_days_back=date.today() - timedelta(days=30))


@app.route('/reset')
def reset():
    saved_stats = dict()
    with open(get_file_path(), 'w+') as f:
        f.write(json.dumps(saved_stats))
    return "reset"


@app.route('/ninety')
def create_90():
    saved_stats = dict()
    with open(get_file_path(), 'r') as f:
        saved_stats = json.load(f)
    i = 0
    for d in range(1, 90):
        cd = date.today() - timedelta(days=d)
        if str(cd) not in saved_stats:
            i += 1
            print(str(cd))
            saved_stats[str(cd)] = get_date_data(cd)
            with open(get_file_path(), 'w+') as f:
                f.write(json.dumps(saved_stats))
            if i > 7:
                break
    return "done"


@app.route('/seven')
def create_7():
    saved_stats = dict()
    with open(get_file_path(), 'r') as f:
        saved_stats = json.load(f)
    for d in range(1, 7):
        cd = date.today() - timedelta(days=d)
        if str(cd) not in saved_stats:
            print(str(cd))
            saved_stats[str(cd)] = get_date_data(cd)
            with open(get_file_path(), 'w+') as f:
                f.write(json.dumps(saved_stats))
    return "done"


@app.route('/status')
def get_status():
    saved_stats = dict()
    if not path.exists(get_file_path()):
        with open(get_file_path(), 'w+') as f:
            f.write(json.dumps(saved_stats))
    with open(get_file_path(), 'r') as f:
        saved_stats = json.load(f)
    yesterday = date.today() - timedelta(days=1)
    if str(yesterday) not in saved_stats:
        saved_stats[str(yesterday)] = get_date_data(
            yesterday)
        with open(get_file_path(), 'w+') as f:
            f.write(json.dumps(saved_stats))
    return jsonify(list(saved_stats.values()))


@app.route('/today')
def get_today():
    saved_stats = dict()
    if not path.exists(get_file_path()):
        with open(get_file_path(), 'w+') as f:
            f.write(json.dumps(saved_stats))
    with open(get_file_path(), 'r') as f:
        saved_stats = json.load(f)
    yesterday = date.today() - timedelta(days=1)
    if str(yesterday) not in saved_stats:
        saved_stats[str(yesterday)] = get_date_data(
            yesterday)
        with open(get_file_path(), 'w+') as f:
            f.write(json.dumps(saved_stats))
    saved_stats[str(date.today())] = get_date_data(date.today())
    return jsonify(list(saved_stats.values()))


def get_date_data(date):
    tomorrow = date + timedelta(days=1)
    print(date)
    folio_client = FolioClient(
        os.environ['OKAPI_URL'],
        os.environ['TENANT_ID'],
        os.environ['FOLIO_USERNAME'],
        os.environ['FOLIO_PASSWORD'])
    definitions = list()
    with open('stats_definitions.json') as jf:
        definitions = json.load(jf)
    print(len(definitions))
    res = dict()
    res['date'] = str(date)
    for defi in definitions:
        print(defi)
        date_q = date if defi['when'] == "today" else tomorrow
        path = defi['path'].format(date_q)
        name = defi['name']
        res[name] = folio_client.folio_get_single_object(path)['totalRecords']
        print(defi)
    return res


@app.route('/totals')
def get_totals():
    folio_client = FolioClient(
        os.environ['OKAPI_URL'],
        os.environ['TENANT_ID'],
        os.environ['FOLIO_USERNAME'],
        os.environ['FOLIO_PASSWORD'])
    loans_path = "/circulation/loans?limit=0"
    requests_path = "/circulation/requests?limit=0"
    users_path = "/users?limit=0"
    instances_path = "/instance-storage/instances?limit=0"
    holdings_path = "/holdings-storage/holdings?limit=0"
    items_path = "/item-storage/items?limit=0"
    return jsonify({'total_users': folio_client.folio_get_single_object(users_path)['totalRecords'],
                    'total_loans': folio_client.folio_get_single_object(loans_path)['totalRecords'],
                    'total_requests': folio_client.folio_get_single_object(requests_path)['totalRecords'],
                    'total_instances': folio_client.folio_get_single_object(instances_path)['totalRecords'],
                    'total_holdings': folio_client.folio_get_single_object(holdings_path)['totalRecords'],
                    'total_items': folio_client.folio_get_single_object(items_path)['totalRecords'],
                    })


@app.errorhandler(Exception)
def handle_error(e):
    code = 500
    if isinstance(e, HTTPException):
        code = e.code
    print("Error: {}".format(e))
    empty = {
        'Item': {
            'Item_no': None,
            'UniqueItemId': None,
            'Location': None,
            'Call_No': None,
            'Loan_Policy': None,
            'Status': 'Okänd',
            "Status_Date_Description": None,
            "Status_Date": None
        }
    }
    empty_root = dicttoxml(
        empty, custom_root='Item_Information', attr_type=False)
    return Response(empty_root, mimetype='text/xml')
    # raise e


def create_rtac_response(folio_client, bib_id):
    query = ('?query=(identifiers=/@value/@identifierTypeId="4f3c4c2c-8b04-4b54-9129-f732f1eb3e14" "{}" or identifiers=/@value/@identifierTypeId="28c170c6-3194-4cff-bfb2-ee9525205cf7" "{}")')
    path = "/instance-storage/instances"
    q = query.format(bib_id, bib_id)
    print(f"looking for instances with Libris ids: {q}")
    instances = folio_client.folio_get(path, "instances", q)
    instance_id = instances[0]['id']
    holdings = folio_client.folio_get('/rtac/{}'.format(instance_id),
                                      "holdings")
    i = 0
    for holding in holdings:
        i += 1
        date = holding.get('dueDate', '')[:10]
        my_dict = {
            'Item_no': 1,
            'UniqueItemId': holding.get('id', ''),
            'Location': holding.get('location', ''),
            'Call_No': holding.get('callNumber', ''),
            'Loan_Policy': '',
            'Status': holding.get('status', ''),
            "Status_Date_Description": None,
            "Status_Date": date
        }
        yield dicttoxml(my_dict, custom_root='Item', attr_type=False)
