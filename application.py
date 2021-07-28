import json
import os
import os.path
from datetime import date, timedelta
from os import path
import time

from werkzeug.utils import header_property
from requests_futures.sessions import FuturesSession
from concurrent.futures import as_completed

from werkzeug.datastructures import Headers

from dicttoxml import dicttoxml
from flask import Flask, Response, jsonify, render_template, request
from folioclient.FolioClient import FolioClient
from lxml import etree
from werkzeug.exceptions import HTTPException

application = Flask(__name__)


def get_file_path():
    path_debug = os.environ.get("DATA_FOLDER_PATH", "/MADE_UP")
    path_real = "/home"
    if os.path.exists(path_debug):
        return os.path.join(path_debug, "stats.json")
    if os.path.exists(path_real):
        return os.path.join(path_real, "stats.json")
    raise Exception("None of the paths exists")


@application.route("/rtac", methods=["GET"])
def rtac():
    folio_client = FolioClient(
        os.environ["OKAPI_URL"],
        os.environ["TENANT_ID"],
        os.environ["FOLIO_USERNAME"],
        os.environ["FOLIO_PASSWORD"],
    )
    bib_id = request.args.get("Bib_ID")
    onr = request.args.get("ONR")
    issn = request.args.get("ISSN")
    isbn = request.args.get("ISBN")
    resp = create_rtac_response(folio_client, bib_id)
    if not bib_id:
        raise ValueError("bib id missing. other identifiers not yet implemented")

    root = etree.Element("Item_Information")
    for itemd in resp:
        item = etree.fromstring(itemd)
        root.append(item)
    return Response(etree.tostring(root), mimetype="text/xml")


@application.route("/")
def hello_world():
    return "RTAC  and statistics app from FOLIO"


@application.route("/statistics/")
@application.route("/statistics/<date>")
def hi(date=date.today()):
    definitions = []
    with open("stats_definitions.json") as jf:
        definitions = json.load(jf)
    names = [f["name"] for f in definitions]
    names.sort()
    return render_template(
        "stats_main.html",
        date=date,
        measures=names,
        seven_days_back=date.today() - timedelta(days=7),
        thirty_days_back=date.today() - timedelta(days=30),
    )


@application.route("/reset")
def reset():
    saved_stats = {}
    with open(get_file_path(), "w+") as f:
        f.write(json.dumps(saved_stats))
    return "reset"


@application.route("/ninety")
async def create_90():

    folio_client = get_folio_client()
    saved_stats = {}
    with open(get_file_path(), "r") as f:
        saved_stats = json.load(f)
    i = 0
    for d in range(1, 90):
        cd = date.today() - timedelta(days=d)
        if str(cd) not in saved_stats:
            i += 1
            print(str(cd))
            saved_stats[str(cd)] = await get_date_data(cd, folio_client)
            with open(get_file_path(), "w+") as f:
                f.write(json.dumps(saved_stats))
            if i > 7:
                break
    return "done"


def get_folio_client():
    return FolioClient(
        os.environ["OKAPI_URL"],
        os.environ["TENANT_ID"],
        os.environ["FOLIO_USERNAME"],
        os.environ["FOLIO_PASSWORD"],
    )


@application.route("/seven")
async def create_7():
    saved_stats = {}
    folio_client = get_folio_client()
    with open(get_file_path(), "r") as f:
        saved_stats = json.load(f)
    for d in range(1, 7):
        cd = date.today() - timedelta(days=d)
        if str(cd) not in saved_stats:
            print(str(cd))
            saved_stats[str(cd)] = await get_date_data(cd, folio_client)
            with open(get_file_path(), "w+") as f:
                f.write(json.dumps(saved_stats))
    return "done"


@application.route("/status")
async def get_status():
    saved_stats = {}
    folio_client = get_folio_client()
    if not path.exists(get_file_path()):
        with open(get_file_path(), "w+") as f:
            f.write(json.dumps(saved_stats))
    with open(get_file_path(), "r") as f:
        saved_stats = json.load(f)
    yesterday = date.today() - timedelta(days=1)
    if str(yesterday) not in saved_stats:
        saved_stats[str(yesterday)] = await get_date_data(yesterday, folio_client)
        with open(get_file_path(), "w+") as f:
            f.write(json.dumps(saved_stats))
    return jsonify(list(saved_stats.values()))


@application.route("/today")
async def get_today():
    saved_stats = {}
    folio_client = get_folio_client()
    if not path.exists(get_file_path()):
        with open(get_file_path(), "w+") as f:
            f.write(json.dumps(saved_stats))
    with open(get_file_path(), "r") as f:
        saved_stats = json.load(f)
    yesterday = date.today() - timedelta(days=1)
    if str(yesterday) not in saved_stats:
        saved_stats[str(yesterday)] = await get_date_data(yesterday, folio_client)
        with open(get_file_path(), "w+") as f:
            f.write(json.dumps(saved_stats))
    saved_stats[str(date.today())] = await get_date_data(date.today(), folio_client)
    return jsonify(list(saved_stats.values()))


async def get_date_data(date, folio_client: FolioClient):
    tomorrow = date + timedelta(days=1)
    print(date)
    definitions = []
    with open("stats_definitions.json") as jf:
        definitions = json.load(jf)
    res = {"date": str(date)}
    session = FuturesSession()
    futures = []
    for idx, defi in enumerate(definitions):
        date_q = date if defi["when"] == "today" else tomorrow
        path = defi["path"].format(date_q)
        try:
            url = folio_client.okapi_url + path
            future = session.get(url, headers=folio_client.okapi_headers)
            future.idx = idx
            future.path = path
            future.namet = defi["name"]
            future.tic = time.perf_counter()
            futures.append(future)
        except Exception as ee:
            print(f"{ee} {path}")
            raise ee

    for idx, future in enumerate(as_completed(futures)):
        toc = time.perf_counter()
        resp = future.result()
        print(
            f"completed {future.idx} {future.path} in {toc - future.tic:0.4f}s {resp.json()['totalRecords']}"
        )
        res[future.namet] = resp.json()["totalRecords"]
    return res


@application.route("/totals")
def get_totals():
    folio_client = FolioClient(
        os.environ["OKAPI_URL"],
        os.environ["TENANT_ID"],
        os.environ["FOLIO_USERNAME"],
        os.environ["FOLIO_PASSWORD"],
    )
    loans_path = "/circulation/loans?limit=0"
    requests_path = "/circulation/requests?limit=0"
    users_path = "/users?limit=0"
    instances_path = "/instance-storage/instances?limit=0"
    holdings_path = "/holdings-storage/holdings?limit=0"
    items_path = "/item-storage/items?limit=0"
    return jsonify(
        {
            "total_users": folio_client.folio_get_single_object(users_path)[
                "totalRecords"
            ],
            "total_loans": folio_client.folio_get_single_object(loans_path)[
                "totalRecords"
            ],
            "total_requests": folio_client.folio_get_single_object(requests_path)[
                "totalRecords"
            ],
            "total_instances": folio_client.folio_get_single_object(instances_path)[
                "totalRecords"
            ],
            "total_holdings": folio_client.folio_get_single_object(holdings_path)[
                "totalRecords"
            ],
            "total_items": folio_client.folio_get_single_object(items_path)[
                "totalRecords"
            ],
        }
    )


@application.errorhandler(Exception)
def handle_error(e):
    if "/rtac" in request.url:
        empty = {
            "Item": {
                "Item_no": None,
                "UniqueItemId": None,
                "Location": None,
                "Call_No": None,
                "Loan_Policy": None,
                "Status": "Okänd",
                "Status_Date_Description": None,
                "Status_Date": None,
            }
        }
        empty_root = dicttoxml(empty, custom_root="Item_Information", attr_type=False)
        return Response(empty_root, mimetype="text/xml")
    return jsonify(error=str(e))


def create_rtac_response(folio_client, bib_id):
    query = '?query=(identifiers=/@value/@identifierTypeId="4f3c4c2c-8b04-4b54-9129-f732f1eb3e14" "{}" or identifiers=/@value/@identifierTypeId="28c170c6-3194-4cff-bfb2-ee9525205cf7" "{}")'
    path = "/instance-storage/instances"
    q = query.format(bib_id, bib_id)
    print(f"looking for instances with Libris ids: {q}")
    instances = folio_client.folio_get(path, "instances", q)
    instance_id = instances[0]["id"]
    holdings = folio_client.folio_get("/rtac/{}".format(instance_id), "holdings")
    for i, holding in enumerate(holdings):
        date = holding.get("dueDate", "")[:10]
        my_dict = {
            "Item_no": 1,
            "UniqueItemId": holding.get("id", ""),
            "Location": holding.get("location", ""),
            "Call_No": holding.get("callNumber", ""),
            "Loan_Policy": "",
            "Status": holding.get("status", ""),
            "Status_Date_Description": None,
            "Status_Date": date,
        }
        yield dicttoxml(my_dict, custom_root="Item", attr_type=False)
