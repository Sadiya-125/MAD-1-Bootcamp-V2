from flask import Blueprint, render_template

from helpers import admin_required

bp = Blueprint("admin", __name__)


@bp.route("/admin/area")
@admin_required
def area():
    return render_template("role_check.html", area="Admin")
