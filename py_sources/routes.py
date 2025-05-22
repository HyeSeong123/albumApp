from flask import Blueprint, render_template
""" from .models import Album """

main = Blueprint("main", __name__)

@main.route("/")
def home():
    return render_template("main.html", message="test")

@main.route("/upload_page")
def upload_page():
    return render_template("upload_page.html", message="test")