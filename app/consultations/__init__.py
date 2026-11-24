from flask import Blueprint
bp = Blueprint("consultations", __name__)
from app.consultations import routes
