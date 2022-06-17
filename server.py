from json import loads as loadjson
from flask import Flask, Markup, render_template, request, redirect, url_for
from flask_cors import CORS
from basex_interact import catch_process_query

app = Flask(__name__)
CORS(app)

 
@app.route("/", methods=["GET", "POST"]) 
def index():
    if request.method == 'POST':
        author = request.form['author']
        title = request.form['title']
        notes_json = loadjson(request.form['payload'])
        searchresult, result_count, mxml_strings, result = catch_process_query(author, title, notes_json)
        showcolumns = "margin-top: 0" if result_count else "display: none"
        return render_template("results.html.j2", searchresult=searchresult, result_count=result_count,
                               mxml_strings=mxml_strings, result=result, showcolumns=showcolumns)
    return render_template("index.html.j2")


if __name__ == '__main__': 
    app.run(debug=True, port=8888)

