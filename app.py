import json
import math
import os
from datetime import date
from flask import Flask, render_template, request, jsonify, send_from_directory
from werkzeug.utils import secure_filename

app = Flask(__name__)

SAVE_FILE = os.path.join(os.path.dirname(__file__), "budget_data.json")
UPLOAD_FOLDER = os.path.join(os.path.dirname(__file__), "static", "uploads")
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY")

if SUPABASE_URL and SUPABASE_KEY:
    from supabase import create_client
    sb = create_client(SUPABASE_URL, SUPABASE_KEY)
    USE_SUPABASE = True
else:
    USE_SUPABASE = False


STATE_TAX_RATES = {
    "AL": 4.0, "AK": 0.0, "AZ": 5.6, "AR": 6.5, "CA": 7.25,
    "CO": 2.9, "CT": 6.35, "DE": 0.0, "FL": 6.0, "GA": 4.0,
    "HI": 4.0, "ID": 6.0, "IL": 6.25, "IN": 7.0, "IA": 6.0,
    "KS": 6.5, "KY": 6.0, "LA": 4.45, "ME": 5.5, "MD": 6.0,
    "MA": 6.25, "MI": 6.0, "MN": 6.875, "MS": 7.0, "MO": 4.225,
    "MT": 0.0, "NE": 5.5, "NV": 6.85, "NH": 0.0, "NJ": 6.625,
    "NM": 5.125, "NY": 4.0, "NC": 4.75, "ND": 5.0, "OH": 5.75,
    "OK": 4.5, "OR": 0.0, "PA": 6.0, "RI": 7.0, "SC": 6.0,
    "SD": 4.5, "TN": 7.0, "TX": 6.25, "UT": 4.85, "VT": 6.0,
    "VA": 5.3, "WA": 6.5, "WV": 6.0, "WI": 5.0, "WY": 4.0, "DC": 6.0
}


def load_data():
    if USE_SUPABASE:
        result = sb.table("budget_data").select("*").eq("id", 1).execute()
        if result.data:
            row = result.data[0]
            return {
                "goals": row.get("goals") or [],
                "background": row.get("background"),
                "state": row.get("state"),
                "tax_rate": row.get("tax_rate"),
                "away_periods": row.get("away_periods") or [],
            }
        return {"goals": [], "background": None, "state": None, "tax_rate": None, "away_periods": []}
    if os.path.exists(SAVE_FILE):
        with open(SAVE_FILE, "r") as f:
            return json.load(f)
    return {"goals": [], "background": None, "state": None, "tax_rate": None, "away_periods": []}


def save_data(data):
    if USE_SUPABASE:
        result = sb.table("budget_data").select("id").eq("id", 1).execute()
        payload = {
            "goals": data.get("goals", []),
            "background": data.get("background"),
            "state": data.get("state"),
            "tax_rate": data.get("tax_rate"),
            "away_periods": data.get("away_periods", []),
        }
        if result.data:
            sb.table("budget_data").update(payload).eq("id", 1).execute()
        else:
            sb.table("budget_data").insert({"id": 1, **payload}).execute()
        return
    with open(SAVE_FILE, "w") as f:
        json.dump(data, f)


@app.route("/manifest.json")
def manifest():
    return send_from_directory("static", "manifest.json", mimetype="application/manifest+json")


@app.route("/sw.js")
def service_worker():
    return send_from_directory("static", "sw.js", mimetype="application/javascript")


def calc_adjusted_months(needed, spendable, away_periods):
    """
    Walk month by month from today. For each month, calculate how much
    can be saved based on how many days are away vs at home.
    Returns (months_count, away_months_info).
    """
    if spendable <= 0 or needed <= 0:
        return None, []

    saved = 0.0
    months = 0
    today = date.today()
    away_hits = []

    while saved < needed and months < 240:
        check = date(today.year + (today.month - 1 + months) // 12,
                     (today.month - 1 + months) % 12 + 1, 1)
        # Days in this month
        if check.month == 12:
            days_in_month = (date(check.year + 1, 1, 1) - check).days
        else:
            days_in_month = (date(check.year, check.month + 1, 1) - check).days

        away_days = 0
        for period in away_periods:
            p_start = date.fromisoformat(period["start"])
            p_end   = date.fromisoformat(period["end"])
            # Overlap with this calendar month
            overlap_start = max(check, p_start)
            overlap_end   = min(date(check.year + (check.month == 12),
                                     check.month % 12 + 1, 1) - date.resolution, p_end)
            if overlap_start <= overlap_end:
                days = (overlap_end - overlap_start).days + 1
                away_days += days
                away_hits.append({
                    "month": check.strftime("%B %Y"),
                    "event": period["name"],
                    "days_away": days,
                })

        home_fraction = max(0, (days_in_month - away_days) / days_in_month)
        saved += spendable * home_fraction
        months += 1

    return round(months, 1), away_hits


@app.route("/")
def index():
    data = load_data()
    return render_template("index.html", goals=data["goals"], background=data.get("background"), state=data.get("state"), tax_rate=data.get("tax_rate"), away_periods=data.get("away_periods", []))


@app.route("/save-state", methods=["POST"])
def save_state():
    body = request.json
    state = body.get("state", "").upper().strip()
    tax_rate = STATE_TAX_RATES.get(state)
    if tax_rate is None:
        return jsonify({"error": "Unknown state"}), 400
    data = load_data()
    data["state"] = state
    data["tax_rate"] = tax_rate
    save_data(data)
    return jsonify({"state": state, "tax_rate": tax_rate})


@app.route("/calculate", methods=["POST"])
def calculate():
    body = request.json
    balance = float(body["balance"])
    monthly_income = float(body["monthly_income"])
    monthly_expenses = float(body["monthly_expenses"])
    spendable = monthly_income - monthly_expenses
    goals = body["goals"]
    today = date.today().isoformat()

    saved_data = load_data()
    saved_goals = {g["name"]: g for g in saved_data.get("goals", [])}
    away_periods = saved_data.get("away_periods", [])

    total_monthly_payments = 0
    results = []

    tax_rate = float(body.get("tax_rate") or 0)

    for goal in goals:
        name = goal["name"]
        base_cost = float(goal["cost"])
        cost = round(base_cost * (1 + tax_rate / 100), 2)
        tax_amount = round(cost - base_cost, 2)
        plan_type = goal.get("plan_type", "save")
        monthly_payment = float(goal.get("monthly_payment") or 0)
        needed = cost - balance

        added_on = goal.get("added_on") or saved_goals.get(name, {}).get("added_on") or today
        goal["added_on"] = added_on

        if needed <= 0:
            results.append({"name": name, "already_have": True, "plan_type": plan_type})
            continue

        if plan_type == "save":
            months_to_save = needed / spendable if spendable > 0 else None
            adjusted_months, away_hits = calc_adjusted_months(needed, spendable, away_periods)

            added_date = date.fromisoformat(added_on)
            today_date = date.today()
            months_elapsed = (today_date.year - added_date.year) * 12 + (today_date.month - added_date.month)
            months_remaining = max(0, round((adjusted_months or months_to_save or 0) - months_elapsed, 1))

            results.append({
                "name": name,
                "already_have": False,
                "plan_type": "save",
                "needed": round(needed, 2),
                "cost": cost,
                "tax_amount": tax_amount,
                "months_to_save": adjusted_months or (round(months_to_save, 1) if months_to_save else None),
                "months_remaining": months_remaining,
                "months_elapsed": months_elapsed,
                "added_on": added_on,
                "away_hits": away_hits,
            })

        else:
            num_payments = math.ceil(needed / monthly_payment) if monthly_payment > 0 else None
            total_paid = monthly_payment * num_payments if num_payments else None
            can_afford = spendable >= monthly_payment
            total_monthly_payments += monthly_payment if can_afford else 0

            results.append({
                "name": name,
                "already_have": False,
                "plan_type": "payment",
                "needed": round(needed, 2),
                "cost": cost,
                "tax_amount": tax_amount,
                "monthly_payment": monthly_payment,
                "num_payments": num_payments,
                "total_paid": round(total_paid, 2) if total_paid else None,
                "can_afford": can_afford,
                "leftover": round(spendable - monthly_payment, 2),
                "shortage": round(monthly_payment - spendable, 2),
            })

    left_after_all = round(spendable - total_monthly_payments, 2)
    weekly = spendable * 12 / 52
    daily = spendable * 12 / 365

    saved_data["goals"] = goals
    save_data(saved_data)

    return jsonify({
        "results": results,
        "saved_goals": goals,
        "summary": {
            "spendable": round(spendable, 2),
            "total_monthly_payments": round(total_monthly_payments, 2),
            "left_after_all": left_after_all,
            "weekly": round(weekly, 2),
            "daily": round(daily, 2),
        }
    })


@app.route("/upload-background", methods=["POST"])
def upload_background():
    file = request.files.get("background")
    if not file:
        return jsonify({"error": "No file provided"}), 400

    filename = secure_filename(file.filename)
    file.save(os.path.join(UPLOAD_FOLDER, filename))

    data = load_data()
    data["background"] = f"uploads/{filename}"
    save_data(data)

    return jsonify({"background": f"uploads/{filename}"})


@app.route("/delete-goal", methods=["POST"])
def delete_goal():
    body = request.json
    index = body["index"]
    data = load_data()
    data["goals"].pop(index)
    save_data(data)
    return jsonify({"ok": True})


if __name__ == "__main__":
    app.run(debug=True, port=8080, host="0.0.0.0")
