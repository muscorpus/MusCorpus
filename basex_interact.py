import re
import pickle
from thefuzz import fuzz
from lxml import etree
from flask import Markup
from BaseXClient import BaseXClient



class MCNote:
    def __init__(self):
        self.__exists_str = '%sexists($w[%s]/%s)%s'
        self.__cond_str = '$w[%s]/%s="%s"'

        self.is_rest = False
        self.is_wildcard = False
        self.duration = None
        self.octave = None
        self.key = None
        self.is_chord = False
        self.alteration = None
        self.has_dot = False
    
    def __str__(self):
        if self.is_wildcard:
            return self.__exists_str % ("not(", "%s", "chord", ")")
        _conditions = []
        if self.duration is not None:
            _conditions += [self.__cond_str % ("%s", "type", self.duration)]
        if self.is_rest:
            _conditions += [self.__exists_str % ("", "%s", "rest", "")]
            return " and ".join(_conditions)
        _conditions += [self.__exists_str % ("not(", "%s", "rest", ")")]
        _conditions += [self.__cond_str % ("%s", "pitch/step", self.key)]
        _conditions += [self.__exists_str % ("" if self.is_chord else "not(", "%s", "chord", "" if self.is_chord else ")")]
        _conditions += [self.__exists_str % ("" if self.has_dot else "not(", "%s", "dot", "" if self.has_dot else ")")]
        if self.alteration:
            _conditions += [self.__cond_str[:-4] % ("%s", "pitch/alter") + str(self.alteration)]
        else:
            _conditions += [self.__exists_str % ("not(", "%s", "pitch/alter", ")")]
        if self.octave is not None:
            _conditions += [self.__cond_str[:-4] % ("%s", "octave") + str(self.octave)]
        return " and ".join(_conditions)


with open("global_reference.pkl", "rb") as inp:
    corpus_reference = pickle.load(inp)


def build_xquery(notes_object):
    duration_dict = {
        1: "whole",
        2: "half",
        4: "quarter",
        8: "eighth",
        16: "16th",
        32: "32nd",
        64: "64th",
        128: "128th"
    }
    alteration_dict = {
        "bb": -2,
        "b": -1,
        "n": None,
        "#": 1,
        "##": 2
    }

    _dd = duration_dict
    _ad = alteration_dict
    _no = notes_object
    notes = []

    if not _no:
        return 0, ""
    
    if not _no["notes"]:
        return 0, ""

    for stave in _no["notes"]:
        _entered_chord = False
        _stave_notes = []
        for note in stave["keys"]:          
            n = MCNote()
            if stave["duration"] == 32:
                n.is_wildcard = True
                notes.append(n)
                break
            if _no["keep_durations"]:
                n.duration = _dd[stave["duration"]]
            if stave["noteType"] == "r":
                n.is_rest = True
                notes.append(n)
                break
            n.key = note["key"]
            if _no["keep_octaves"]:
                n.octave = note["octave"]
            if _entered_chord:
                n.is_chord = True
            _stave_notes.append(n)
            _entered_chord = True
        for modifier in stave["modifiers"]:
            if modifier["type"] == "dot":
                _stave_notes[modifier["index"]].has_dot = True
            else:
                _stave_notes[modifier["index"]].alteration = _ad[modifier["type"]]
        notes += _stave_notes

    
    if all(note.is_wildcard for note in notes):
        return 0, ""

    note_conditions = []
    for i, n in enumerate(notes):
        _condition = str(n)
        _format_str = [str(i + 1)] * _condition.count("%s")
        note_conditions.append(_condition % tuple(_format_str))
    
    context = """(
      for sliding window $ww in $w
        start at $s-pos when true()
        only end at $e-pos when $e-pos - $s-pos eq 1
        return if ($ww[1]/.. != $ww[2]/..)
          then $ww[2]/..
          else ()
    )"""
    if len(notes) == 1:
        context = "$w[1]/.."
    note_condition_str = "\n      and ".join(note_conditions)
    query = """for sliding window $w in collection("metacorpus")//note
    start at $s when true()
    only end at $e when $e - $s eq %s-1
    let $precontext := ($w[1]/../preceding-sibling::*)[last()]
    let $context := %s
    let $postcontext := ($w[%s]/../following-sibling::*)[1]
    return if (
      %s
      )
    then
    <result><path>{db:path($w[1])}</path><attribs>{$w[1]/../../measure[1]/attributes}</attribs><first>{$w[1]}</first><payload><score-partwise version="4.0"><part-list><score-part id="P1"><part-name>Music</part-name></score-part></part-list><part id="P1">{$precontext}{$w[1]/..}{$context}{$postcontext}</part></score-partwise></payload></result>
    else ()""" % (str(len(notes)), context, str(len(notes)), note_condition_str)
    return len(notes), query


def basex_search(_query):
    session = BaseXClient.Session('localhost', 1984, 'admin', 'admin')

    try:
        query = session.query(_query)
        res = [hit[1] for hit in query.iter()]
        query.close()
        return res

    finally:
        # close session
        if session:
            session.close()


def _notes_equal(e1, e2):
    return re.sub(r"\s*", "", etree.tostring(e1).decode(encoding="utf-8")).lower() == re.sub(r"\s*", "", etree.tostring(e2).decode(encoding="utf-8")).lower()


def process_single_output(excerpt, notes_queried):

    tree = etree.fromstring(excerpt)
    _uri = str(tree.xpath("./path/text()")[0])
    
    first_measure = tree.xpath("./payload/score-partwise/part/measure")[0]
    if first_measure.xpath("./attributes"):
        old_attrs = first_measure.xpath("./attributes")[0]
        first_measure.remove(old_attrs)
    first_measure.insert(0, tree.xpath("./attribs/attributes")[0])
    
    _started = 0
    part = tree.xpath("./payload/score-partwise/part")[0]
    for el in [elem for measure in part for elem in measure]:
        if el.tag != 'note':
            continue
        if (_started == notes_queried) or (not _notes_equal(el, tree.xpath("./first/note")[0]) and not _started):
            continue
        el.attrib["color"] = "#FF0000"
        _started += 1
    
    return {
        "uri": _uri,
        "musicxml": '<?xml version="1.0" encoding="UTF-8" standalone="no"?>\n' +
                    etree.tostring(tree.xpath("./payload/score-partwise")[0]).decode(encoding="utf-8").strip()
    }


def _build_mxmls_list(mxmls_list):
    return ",\n".join(["'" + mxml.replace("\n", "\\n").replace("'", "\\'") + "'" for mxml in mxmls_list])


def _retrieve_info_from_uri(uri):
    global corpus_reference
    if uri not in corpus_reference:
        return {
        "title": re.sub(r"\.(xml|mxl|musicxml)$", "", uri.split("/")[-1]).replace("_", " "),
        "title_link": "#",
        "author": "Unknown",
        "author_link": "#"
        }
    return {
        "title": re.sub(r"\.(xml|mxl|musicxml)$", "", corpus_reference[uri]["title"].split("/")[-1]).replace("_", " "),
        "title_link": corpus_reference[uri]["title_link"] if corpus_reference[uri]["title_link"] else "#",
        "author": corpus_reference[uri]["author"],
        "author_link": corpus_reference[uri]["author_link"] if corpus_reference[uri]["author_link"] else "#"
    }


def catch_process_query(author="", title="", notes_json={}):
    try:
        notes_queried, _query = build_xquery(notes_json)
        if not notes_queried:
            searchresult = "You have entered an empty search term."
            return searchresult, 0, "", []
        _result = basex_search(_query)
        if not _result:
            searchresult = "Your search yielded no results."
            return searchresult, 0, "", []
        searchresult = Markup("<br>")
        compositions = [process_single_output(res, notes_queried) for res in _result]
        compositions_info = [_retrieve_info_from_uri(comp["uri"]) for comp in compositions]
        comp_obj = [(comp, comp_info) for comp, comp_info in zip(compositions, compositions_info)]
        if author or title:
            comp_obj = [(comp, comp_info) for comp, comp_info in comp_obj
                        if (fuzz.partial_ratio(author, comp_info["author"]) > 95 or not author)
                        and (fuzz.partial_ratio(title, comp_info["title"]) > 95 or not title)]
        if not comp_obj:
            searchresult = "Your search yielded no results."
            return searchresult, 0, "", []
        comp_obj = comp_obj[:30]  # Temporary restriction
        compositions, compositions_info = list(zip(*comp_obj))
        mxml_strings = _build_mxmls_list([composition["musicxml"] for composition in compositions])
        result = [compositions_info[0]]
        result[0].update({"div_ids": ["osmdCanvas0"]})
        for i, composition in enumerate(compositions[1:]):
            if compositions_info[i]["author"] == compositions_info[i + 1]["author"] and compositions_info[i]["title"] == compositions_info[i + 1]["title"]:
                result[-1]["div_ids"].append("osmdCanvas" + str(i + 1))
            else:
                _elem = compositions_info[i + 1]
                _elem.update({"div_ids": ["osmdCanvas" + str(i + 1)]})
                result.append(_elem)
        return searchresult, str(len(compositions)) + " results", mxml_strings, result
    except Exception as e:
        searchresult = "There was an error processing your request. " + Markup("<b>{}:</b> {}".format(e.__class__.__name__, str(e)))
        return searchresult, 0, "", []

