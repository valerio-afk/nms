from flask import render_template,current_app
import os

def render_widget(id,**kwargs):
    template_fname = f"card.{id}.html"
    css_fname = f"card.{id}.css"

    return render_template(template_fname,card_id=id,**kwargs), css_fname if os.path.exists(os.path.join(current_app.static_folder,css_fname)) else None


def get_widgets_html(widgets):
    return [w for w,c in widgets]

def get_widgets_css_files(widgets):
    return [c for w,c in widgets if c is not None]