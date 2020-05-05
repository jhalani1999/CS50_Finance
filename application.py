import os
import datetime

from cs50 import SQL
from flask import Flask, flash, jsonify, redirect, render_template, request, session
from flask_session import Session
from tempfile import mkdtemp
from werkzeug.exceptions import default_exceptions, HTTPException, InternalServerError
from werkzeug.security import check_password_hash, generate_password_hash

from helpers import apology, login_required, lookup, usd

# Configure application
app = Flask(__name__)

# Ensure templates are auto-reloaded
app.config["TEMPLATES_AUTO_RELOAD"] = True

# Ensure responses aren't cached
@app.after_request
def after_request(response):
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    response.headers["Expires"] = 0
    response.headers["Pragma"] = "no-cache"
    return response

# Custom filter
app.jinja_env.filters["usd"] = usd

# Configure session to use filesystem (instead of signed cookies)
app.config["SESSION_FILE_DIR"] = mkdtemp()
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"
Session(app)

# Configure CS50 Library to use SQLite database
db = SQL("sqlite:///finance.db")

# Make sure API key is set
if not os.environ.get("API_KEY"):
    raise RuntimeError("API_KEY not set")


@app.route("/")
@login_required
def index():
    """Show portfolio of stocks"""
    values = ["symbol", "name", "share"]
    orders = db.execute("SELECT * FROM countshare WHERE id = :id", id = session["user_id"])
    cash = db.execute("SELECT cash FROM users WHERE id = :id", id = session["user_id"])
    prices = []
    totals = []
    amount = cash[0]["cash"]
    length = len(orders)
    db.execute("DELETE FROM countshare WHERE share <= 0")
    for i in range(length):
        price = lookup(orders[i]["symbol"])["price"]
        prices.append(round(price,2))
        total = float(orders[i]["share"]) * float(price)
        totals.append(round(total,2))
        amount = float(amount) + total
    return render_template("index.html", orders = orders, amount = round(amount,2), price = prices, total = totals, length = length, values = values, cash = round(cash[0]["cash"],2))


@app.route("/buy", methods=["GET", "POST"])
@login_required
def buy():
    """Buy shares of stock"""

    if request.method == "GET":
        return render_template("buy.html")

    else:

        # ensure symbol is provided
        if not request.form.get("symbol"):
            return apology("must provide symbol", 400)

        # ensure shares is provided
        if not request.form.get("shares"):
            return apology("must provide shares", 400)

        # ensure correct symbol is provided
        if lookup(request.form.get("symbol")) == None:
            return apology("symbol does not exist", 400)

        #ensure positive shares
        if int(request.form.get("shares")) <= 0:
            return apology("must provide positive shares", 400)

        symbol = lookup(request.form.get("symbol"))

        cash = db.execute("SELECT cash FROM users WHERE id = :id", id = session["user_id"])

        if float(cash[0]["cash"]) < (float(symbol["price"]) * float(request.form.get("shares"))):
            return apology("CAN'T AFFORD", 400)

        else:

            cash = float(cash[0]["cash"]) - (float(symbol["price"]) * float(request.form.get("shares")))

            # checking for existing symbol
            exist = db.execute("SELECT * FROM countshare WHERE symbol = :symbol",
                                symbol = request.form.get("symbol"))

            # if dymbol does not exist insert
            if len(exist) == 0:
                db.execute("INSERT INTO countshare (id, symbol, name, share) VALUES(:id, :symbol, :name, :share)",
                            id = session["user_id"], symbol = request.form.get("symbol"), name=symbol["name"], share = request.form.get("shares"))

            # otherwise update shares for existing symbol
            else:
                db.execute("UPDATE countshare SET share = :share WHERE id = :id and symbol = :symbol",
                            share = int(exist[0]["share"]) + int(request.form.get("shares")), id = session["user_id"], symbol = request.form.get("symbol"))

            db.execute("INSERT INTO orders (id, name, symbol, share, price, total, time, type) VALUES(:id, :name, :symbol, :share, :price, :total, :time, :types)",
                        id=session["user_id"], name=symbol["name"], symbol=symbol["symbol"], share=request.form.get("shares"), price=symbol["price"], total=(float(symbol["price"]) * float(request.form.get("shares"))), time=datetime.datetime.now(), types = "buy")
            db.execute("UPDATE users SET cash = :cash WHERE id = :id",
                        cash = cash, id = session["user_id"])
            return redirect("/")


@app.route("/history")
@login_required
def history():
    """Show history of transactions"""
    values = ["symbol", "share", "price", "time", "type"]
    history = db.execute("SELECT * FROM orders WHERE id = :id", id = session["user_id"])
    return render_template("history.html", values = values, history = history, length = len(history))


@app.route("/login", methods=["GET", "POST"])
def login():
    """Log user in"""

    # Forget any user_id
    session.clear()

    # User reached route via POST (as by submitting a form via POST)
    if request.method == "POST":

        # Ensure username was submitted
        if not request.form.get("username"):
            return apology("must provide username", 403)

        # Ensure password was submitted
        elif not request.form.get("password"):
            return apology("must provide password", 403)

        # Query database for username
        rows = db.execute("SELECT * FROM users WHERE username = :username",
                          username=request.form.get("username"))

        # Ensure username exists and password is correct
        if len(rows) != 1 or not check_password_hash(rows[0]["hash"], request.form.get("password")):
            return apology("invalid username and/or password", 403)

        # Remember which user has logged in
        session["user_id"] = rows[0]["id"]

        # Redirect user to home page
        return redirect("/")

    # User reached route via GET (as by clicking a link or via redirect)
    else:
        return render_template("login.html")


@app.route("/logout")
def logout():
    """Log user out"""

    # Forget any user_id
    session.clear()

    # Redirect user to login form
    return redirect("/")


@app.route("/quote", methods=["GET", "POST"])
@login_required
def quote():
    """Get stock quote."""
    if request.method == "GET":
        return render_template("quote.html")

    else:
        symbol = lookup(request.form.get("symbol"))
        return render_template("quoted.html", symbol=symbol["symbol"], price=symbol["price"], name=symbol["name"])


@app.route("/cash", methods=["GET", "POST"])
def cash():
    """Add Cash."""
    if request.method == "GET":
        return render_template("addcash.html")

    else:
        cash = int(request.form.get("cash"))
        if cash <= 0:
            return apology("add positive integer", 400)

        else:
            cash_e = db.execute("SELECT cash FROM users WHERE id = :id", id = session["user_id"])
            cash = int(cash_e[0]["cash"]) + cash
            db.execute("UPDATE users SET cash = :cash WHERE id = :id",
                        cash = cash, id = session["user_id"])
            return redirect("/")


@app.route("/register", methods=["GET", "POST"])
def register():
    """Register user"""
    # check using request method for get, if true return register.html
    if request.method == "GET":
        return render_template("register.html")

    # for post method
    else:

        # ensure username is provided
        if not request.form.get("username"):
            return apology("must provide username", 403)

        # Ensure password was submitted
        elif not request.form.get("password"):
            return apology("must provide password", 403)

        # ensure password confirmation is provided
        elif not request.form.get("confirmation"):
            return apology("must provide password check", 403)

        # ensure password matches
        elif request.form.get("confirmation") != request.form.get("password"):
            return apology("password doesn't match", 403)

        rows = db.execute("SELECT * FROM users WHERE username = :username", username=request.form.get("username"))

        if len(rows) == 0:
            db.execute("INSERT INTO users (username, hash) VALUES(:username, :hash)",username=request.form.get("username"), hash=generate_password_hash(request.form.get("password")))
            return render_template("login.html")

        else:
            return apology("username already exist", 403)


@app.route("/sell", methods=["GET", "POST"])
@login_required
def sell():
    """Sell shares of stock"""
    # for get method
    if request.method == "GET":
        #  to get existing symbol to sell(you can't share share if you sont own)
        symbols = db.execute("SELECT symbol FROM countshare WHERE id = :id", id = session["user_id"])
        symbol = []
        for i in range(len(symbols)):
            symbol.append(symbols[i]["symbol"])
        return render_template("sell.html", symbols = symbol)

    #  for post method
    else:

        # ensure symbol is selected
        if not request.form.get("symbol"):
            return apology("missing symbol", 400)

        # ensure share is provided
        elif not request.form.get("shares"):
            return apology("missing shares", 400)

        #  ensure enough share is provided
        share = db.execute("SELECT share FROM countshare WHERE symbol = :symbol AND id = :id", symbol = request.form.get("symbol"), id = session["user_id"])
        if int(request.form.get("shares")) > int(share[0]["share"]):
            return apology("not enough share", 400)

        elif int(request.form.get("shares"))<0:
            return apology("only positive share", 400)

        else:
            symbol = lookup(request.form.get("symbol"))

            # inserting number of share to sell in order table
            db.execute("INSERT INTO orders (id, name, symbol, share, price, total, time, type) VALUES(:id, :name, :symbol, :share, :price, :total, :time, :types)",
                        id=session["user_id"], name=symbol["name"], symbol=symbol["symbol"], share=int(request.form.get("shares")), price=symbol["price"], total=(float(symbol["price"]) * float(request.form.get("shares"))), time=datetime.datetime.now(), types="sell")

            # updating total shares of that stock
            db.execute("UPDATE countshare SET share = :share WHERE id = :id AND symbol = :symbol",
                        share = int(share[0]["share"]) - int(request.form.get("shares")), id = session["user_id"], symbol=request.form.get("symbol"))

            # first know how much cash you have
            cash = db.execute("SELECT cash FROM users WHERE id = :id", id = session["user_id"])
            cash = float(cash[0]["cash"]) + (float(symbol["price"]) * float(request.form.get("shares")))

            # sold share to cash increment
            db.execute("UPDATE users SET cash = :cash WHERE id = :id", cash = cash, id = session["user_id"])

            return redirect("/")


def errorhandler(e):
    """Handle error"""
    if not isinstance(e, HTTPException):
        e = InternalServerError()
    return apology(e.name, e.code)


# Listen for errors
for code in default_exceptions:
    app.errorhandler(code)(errorhandler)