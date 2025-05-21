from flask import Blueprint, render_template
""" from .models import Album """

main = Blueprint("main", __name__)

@main.route("/")
def home():
    return render_template("main.html")