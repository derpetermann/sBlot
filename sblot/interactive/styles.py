blank_axis = {
    "showgrid": False,  # thin lines in the background
    "zeroline": False,  # thick line at x=0
    "visible": False,  # numbers below
}


blank_layout = {
    "xaxis_title": "",
    "yaxis_title": "",
    "xaxis": blank_axis,
    "yaxis": blank_axis,
    "plot_bgcolor": "rgba(0, 0, 0, 0)",
    "paper_bgcolor": "rgba(0, 0, 0, 0)",
}


upload_box_style = {
    "width": "98%",
    "height": "40px",
    "lineHeight": "40px",
    "borderWidth": "1px",
    "borderStyle": "dashed",
    "borderRadius": "6px",
    "textAlign": "center",
    "margin": "4px",
    "font-variant": "small-caps",
    "fontSize": "11pt",
}

tabs_styles = {
    "height": "36px",
    "margin-top": "8px",
    "margin-bottom": "8px",
}

tab_style = {
    "padding": "8px",
    "borderBottom": "1px solid #d6d6d6",
    "fontSize": "11pt",
}

tab_selected_style = {
    "padding": "8px",
    "fontWeight": "bold",
    "fontSize": "11pt",
}

all_tab_styles = {
    "style": tab_style | {"color": "rgb(70,70,70)"},
    "selected_style": tab_selected_style,
    "disabled_style": tab_style,
}