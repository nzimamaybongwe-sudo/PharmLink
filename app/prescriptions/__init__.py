from flask import Blueprint
bp = Blueprint("prescriptions", __name__)
from app.prescriptions import routes
