import os

from cs50 import SQL
from flask import Flask, flash, redirect, render_template, request, session
from flask_session import Session
from tempfile import mkdtemp
from werkzeug.exceptions import default_exceptions
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


@app.route("/")
@login_required
def index():
    """Show portfolio of stocks"""
    # Check list of owned stocks, their amount, and current value
    # Data from users database
    user = db.execute("SELECT username, cash FROM users WHERE id=:id", id=session["user_id"])

    # Data from history database
    stocks = db.execute("SELECT symbol, sum(shares) AS sumShares FROM history WHERE user_id=:id GROUP BY symbol", id=session["user_id"]) # reads from DB and groups by symbol the sum of owned shares

    # Check for current stock price
    for i in range(0, len(stocks)):
        try:
            stocks[i]["price"] = lookup(stocks[i]['symbol'])["price"]
            stocks[i]["name"] = lookup(stocks[i]['symbol'])["name"]
            stocks[i]["total"] = stocks[i]["price"] * stocks[i]["sumShares"]
        except:
            pass

    # Calculate total portfolio value (including cash)
    worth = 0
    for stock in stocks:
        worth += stock["price"] * stock["sumShares"]
    worth += user[0]["cash"]

    # Tidy data
    worth = usd(worth)
    user[0]["cash"] = usd(user[0]["cash"])

    for i in range(0, len(stocks)):
        stocks[i]["price"] = usd(stocks[i]["price"])
        stocks[i]["total"] = usd(stocks[i]["total"])

    return render_template("index.html", user=user, stocks=stocks, worth=worth)


@app.route("/buy", methods=["GET", "POST"])
@login_required
def buy():
    """Buy shares of stock"""
    if request.method == "POST":
        # CHECK IF THE DATA WAS PROPERLY INPUTED

        # Ensure symbol is entered
        if not request.form.get("symbol"):
            return apology("missing symbol", 400)
        # Ensure the number of shares is entered
        if not request.form.get("shares"):
            return apology("number of shares are missing", 400)

        # Ensure the symbol exists
        quote = lookup(request.form.get("symbol"))
        if not quote:
            return apology("Enter a valid share symbol", 400)

        # CHECK USER'S BALANCE

        # Ensure the number of shares is a positive int number
        try:
            shares = int(request.form.get("shares"))
        except:
            return apology("insert a positive number of shares without decimal numbers (integer)", 400)
        if shares < 0:
            return apology("number of shares must be a positive number", 400)

        # Check how much cash does the user have available
        cash = db.execute("SELECT cash FROM users WHERE id = :id",
                          id=session["user_id"])[0]['cash']


        # Check if the user has enough ballance. If not send apology without execution
        if int(cash) <= shares * int(quote["price"]):
            return apology("Your need more cash!!!", 400)

        # UBDATE THE DATABASE

        # Decrease available cash
        shares_value = shares * quote["price"]
        new_cash = cash - shares_value

        # Update the DB with the new value of cash
        db.execute("UPDATE users SET cash = :new_cash where id = :id", new_cash=new_cash, id=session["user_id"])

        # Insert data in the log database
        db.execute("INSERT INTO history (user_id, symbol, shares, share_value) VALUES (:id, :symbol, :shares, :shares_value)", id=session["user_id"], symbol=quote['symbol'], shares=shares, shares_value=shares_value)

        return redirect("/")

    else:
        return render_template("buy.html")


@app.route("/history")
@login_required
def history():
    """Show history of transactions"""
    # Select needed data
    try:
        history = db.execute("SELECT symbol, date, shares, share_value FROM history WHERE user_id=:id", id=session["user_id"])
    except:
        return apology("hmmm", 400)

    # Defining buy/sell status
    for i in range(0, len(history)):
        a = history[i]['shares']
        if a > 0:
            history[i]["status"] = "buy"
        elif a < 0:
            history[i]["status"] = "sell"

    # defining share price
        shares = abs(history[i]["shares"])
        if shares == 1:
            history[i]["sharePrice"] = usd(history[i]["share_value"])

        elif shares >1:
            history[i]["sharePrice"] = usd(history[i]["share_value"]/shares)

    return render_template("history.html", history=history)





@app.route("/login", methods=["GET", "POST"])
def login():
    """Log user in"""

    # Forget any user_id
    session.clear()

    # User reached route via POST (as by submitting a form via POST)
    if request.method == "POST":

        # Ensure username was submitted
        if not request.form.get("username"):
            return apology("must provide username", 400)

        # Ensure password was submitted
        elif not request.form.get("password"):
            return apology("must provide password", 400)

        # Query database for username
        rows = db.execute("SELECT * FROM users WHERE username = :username",
                          username=request.form.get("username"))

        # Ensure username exists and password is correct
        if len(rows) != 1 or not check_password_hash(rows[0]["hash"], request.form.get("password")):
            return apology("invalid username and/or password", 400)

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
    if request.method == "POST":
        symbol = request.form.get("symbol")
        quote = lookup(symbol)

        if not quote:
            return apology("The symbol does not exist", 400)

        else:
            quote["price"] = usd(quote["price"])
            return render_template("quoted.html", quote=quote)

    else:
        return render_template("quote.html")


@app.route("/register", methods=["GET", "POST"])
def register():
    """Register user"""
    # Forget any user_id
    session.clear()

    # User reached route via POST (as by submitting a form via POST)
    if request.method == "POST":
        # CHECK THAT THE FORM IS FULLY FILLED

        # Ensure username was submitted
        if not request.form.get("username"):
            return apology("must provide username", 400)

        # Ensure password was submitted
        elif not request.form.get("password"):
            return apology("must provide password", 400)

        # Ensure password confirmation was submitted
        elif not request.form.get("confirmation"):
            return apology("must provide password confirmation", 400)

        # CHECK IF PASSWORD AND CONFIRMATION ARE THE SAME
        elif not request.form.get("password") == request.form.get("confirmation"):
            return apology("confirmed password is incorrect")

        # CHECK IF THE USRNAME IS AVAILABLE

        # Query database for username
        result = db.execute("SELECT * FROM users WHERE username=:u", u=request.form.get("username"))
        if result:
            return apology("username already in use", 400)
        else:
            username = request.form.get("username")

        # Hash the password
        #hash = pwd_context.encrypt(request.form.get("password"))
        hash = generate_password_hash(request.form.get("password"))


        # INSERT NEW USER IN THE DATABASE
        db.execute("INSERT INTO users (username, hash) VALUES(:u, :h)", u=username, h=hash)

        # Remember which user has logged in
        session["user_id"] = db.execute("SELECT id FROM users WHERE username= :u", u=username)[0]["id"]

        # Redirect user to home page
        return redirect("/")

    # User reached route via GET (as by clicking a link or via redirect)
    else:
        return render_template("register.html")

@app.route("/sell", methods=["GET", "POST"])
@login_required
def sell():
    """Sell shares of stock"""
    if request.method == "POST":

        # CHECK IF THE DATA WAS PROPERLY INPUTED

        # Ensure symbol is entered
        if not request.form.get("symbol"):
            return apology("missing symbol")
        # Ensure the number of shares is entered
        if not request.form.get("shares"):
            return apology("number of shares are missing", 400)

        # Ensure inserted number of shares is a positive int number
        try:
            shares = int(request.form.get("shares"))
        except:
            return apology("insert a positive number of shares without decimal numbers (integer)")

        # CHECK USER'S BALANCE

        # Check how many stocks does the user have available
        symbol = request.form.get("symbol")
        available_shares = db.execute("SELECT symbol, sum(shares) AS sumShares FROM history WHERE user_id=:id AND symbol=:symbol GROUP BY symbol", id=session["user_id"], symbol=symbol)[0]['sumShares']


        # Check if the user has enough ballance. If not send apology without execution
        if available_shares < shares:
            return apology("select fewer shares to sell!!!", 400)

        # UBDATE THE DATABASE
        # get the latest quote
        quote = lookup(symbol)
        # Check how much cash does the user have available
        cash = float("{0:.2f}".format(db.execute("SELECT cash FROM users WHERE id = :id",
                          id=session["user_id"])[0]['cash']))

        # Update new parameters
        shares_value = shares * quote["price"]
        new_cash = cash + shares_value
        new_shares = available_shares - shares

        # Update the DB with the new value of cash
        db.execute("UPDATE users SET cash = :new_cash where id = :id", new_cash=new_cash, id=session["user_id"])

        # Insert data in the log database
        db.execute("INSERT INTO history (user_id, symbol, shares, share_value) VALUES (:id, :symbol, -:shares, :shares_value)", id=session["user_id"], symbol=quote['symbol'], shares=shares, shares_value=shares_value)

        return redirect("/")
        #####################


    else:
        # Get users account status and give existing symbols to be selected

        # Data from history database
        stocks = db.execute("SELECT symbol FROM history WHERE user_id=:id GROUP BY symbol", id=session["user_id"])

        return render_template("sell.html", stocks=stocks)


def errorhandler(e):
    """Handle error"""
    return apology(e.name, e.code)


# listen for errors
for code in default_exceptions:
    app.errorhandler(code)(errorhandler)
