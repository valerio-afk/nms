from typing import Optional, Tuple, List
from flask import render_template, current_app, g
import os

from flask_wtf.csrf import generate_csrf


def render_widget(id:str,**kwargs)->Tuple[str,Optional[str]]:
    template_fname = f"card.{id}.html"
    css_fname = f"card.{id}.css"

    if ("csrf_token" not in kwargs):
        kwargs["csrf_token"] = generate_csrf

    return render_template(template_fname,
                           card_id=id,
                           csp_nonce=g.csp_nonce,
                           **kwargs
                           ), css_fname if os.path.exists(os.path.join(current_app.static_folder,css_fname)) else None


def get_widgets_html(widgets:List[Optional[Tuple[str,Optional[str]]]]) -> List[str]:
    return [x[0] for x in widgets if (x is not None)]

def get_widgets_css_files(widgets:List[Optional[Tuple[str,Optional[str]]]]) -> List[str]:
    return [x[1] for x in widgets if ((x is not None) and (x[1] is not None))]