# convert hex legible json to python private dict
import json
from collections import OrderedDict
from pathlib import Path
from typing import Dict, List


def pydicom_private_dicts_from_json(privates_json_file: Path | str) -> Dict[str, Dict[int, List]]:
    unfiltered_dict = _pydicom_private_dicts_from_json(privates_json_file=privates_json_file)
    filtered_dict = _filter_creators(unfiltered_dict_of_private_dicts=unfiltered_dict)
    return filtered_dict


def _pydicom_private_dicts_from_json(privates_json_file: Path | str) -> Dict[str, Dict[int, List]]:
    """_summary_

    Args:
        privates_json_file (Path | str): _description_

    Returns:
        Dict[str,Dict[int,List]]: key is the private creator, value is the dictionary of private elements
            pydicom.datadict.add_private_dict_entries(key, value) for key,value in returned.items()

    """
    with open(privates_json_file, "r") as f:
        my_list_of_privates_dict = json.load(f)

    my_converted_dict = dict()
    converted_dict_of_privates = dict()

    for private_dict in my_list_of_privates_dict:
        my_converted_dict = dict()
        for creator, dict_of_private_elements in private_dict.items():
            for tag, entry in dict_of_private_elements.items():
                my_converted_dict[int(tag, 16)] = entry
            converted_dict_of_privates[creator] = OrderedDict(sorted(my_converted_dict.items()))
    return converted_dict_of_privates


def _filter_creators(unfiltered_dict_of_private_dicts: Dict[str, Dict[int, List]]) -> Dict[str, Dict[int, List]]:
    not_private_creators = []
    for creator, private_dict in unfiltered_dict_of_private_dicts.items():
        for tag in private_dict.keys():
            group = tag >> 16
            remainder = group % 2
            if remainder == 0:
                hex_string = "{:04X}".format(group)
                print(f"{hex_string} is not an odd value, {creator} will be filtered out")
                not_private_creators.append(creator)
                break

    for creator in not_private_creators:
        del unfiltered_dict_of_private_dicts[creator]

    empty_creators = []
    for creator in unfiltered_dict_of_private_dicts.keys():
        if len(unfiltered_dict_of_private_dicts[creator]) == 0:
            empty_creators.append(creator)

    for creator in empty_creators:
        del unfiltered_dict_of_private_dicts[creator]
    filtered_dict = unfiltered_dict_of_private_dicts
    return filtered_dict


def wrap_in_single_quotes(s: str) -> str:
    return "'" + s + "'"


def generate_python_code_from_private_dict_list(
    pythonic_list_of_private_dicts: List[Dict[str, Dict[int, List]]], for_pydicom_pr=False
) -> str:
    python_code_lines = []
    python_code_lines.append("from typing import Dict, Tuple\n")
    python_code_lines.append("new_private_dictionaries: Dict[str, Dict[str, Tuple[str, str, str, str]]] = {\n")
    converted_dict_of_privates = dict()
    converted_list_of_private_dicts = []
    for pythonic_dict_of_private_dicts in pythonic_list_of_private_dicts:
        for creator, dict_of_private_elements in pythonic_dict_of_private_dicts.items():
            creator_line_of_code = "\t" + wrap_in_single_quotes(creator) + ":" + "{" + "\n"
            python_code_lines.append(creator_line_of_code)
            for tag, entry in dict_of_private_elements.items():
                group = tag >> 16
                element = tag % 65536
                private_byte = element % 256
                hex_tag = "0x" + "{:08X}".format(tag)
                if for_pydicom_pr:
                    hex_tag = "{:04X}".format(group) + "xx" + "{:02X}".format(private_byte)
                vr = entry[0]
                vm = entry[1]
                private_name = entry[2]
                retired = entry[3]
                single_quote = "'"
                comma = ","
                quoted_hex_tag = hex_tag
                if for_pydicom_pr:
                    quoted_hex_tag = wrap_in_single_quotes(hex_tag)
                item_pair = (
                    "\t\t"
                    + quoted_hex_tag
                    + ": ("
                    + wrap_in_single_quotes(vr)
                    + comma
                    + wrap_in_single_quotes(vm)
                    + comma
                    + wrap_in_single_quotes(private_name)
                    + comma
                    + wrap_in_single_quotes(retired)
                    + "),  # noqa\n"
                )
                python_code_lines.append(item_pair)
                # example line from _private_dict.py in pydicom
                # '7043xx10': ('LO', '1', 'Philips NM Private Group', ''),  # noqa
            close_creator_line_of_code = "\t},\n"
            python_code_lines.append(close_creator_line_of_code)
    close_dictionary_line_of_code = "}\n"
    python_code_lines.append(close_dictionary_line_of_code)
    return "".join(python_code_lines)


def jsonify_pydicom_private_dict_list(
    pythonic_list_of_private_dicts: List[Dict[str, Dict[int, List]]]
) -> List[Dict[str, Dict[str, List]]]:
    """For conversion of an existing list of pythonic private dictionaries so that json.dump(jsonic_list_of_private_dict) will be
    of the same format as the rest of this module uses to deserialize a private dictionary from JSON.
    Probably will be a list of one, but... keeps the logic consistent and makes for easier merging of json.

    Args:
        pythonic_dict (Dict[str,Dict[int,List]]): The list of private dictionaries in the format that pydicom requires

    Returns:
        Dict[str,Dict[str,List]]: The list of private dictionaries that produces a JSON file with hex attributes.
    """
    my_jsonified_dict = dict()
    converted_dict_of_privates = dict()
    converted_list_of_private_dicts = []
    for pythonic_dict_of_private_dicts in pythonic_list_of_private_dicts:
        for creator, dict_of_private_elements in pythonic_dict_of_private_dicts.items():
            for tag, entry in dict_of_private_elements.items():
                hex_tag = "0x" + "{:08X}".format(tag)
                my_jsonified_dict[hex_tag] = entry
            converted_dict_of_privates[creator] = my_jsonified_dict
            my_jsonified_dict = {}
            converted_list_of_private_dicts.append({creator: converted_dict_of_privates[creator]})

    return converted_list_of_private_dicts


if __name__ == "__main__":
    from impac_privates import impac_private_dict
    from pydicom import datadict

    rs_impac_dict = {}
    converted_dict_of_privates = pydicom_private_dicts_from_json("privates_list.json")
    # print(converted_dict_of_privates)
    for private_creator, private_element_dictionary in converted_dict_of_privates.items():
        try:
            if private_creator == "IMPAC":
                rs_impac_set = set(private_element_dictionary)
                impac_set = set(impac_private_dict)
                set_diff = rs_impac_set ^ impac_set
                set_union = rs_impac_set | impac_set
                for key in set_union:
                    print(f"{'{:08X}'.format(key)}")
                    if key in private_element_dictionary:
                        print(f"RS: {private_element_dictionary[key]}")
                    if key in impac_private_dict:
                        print(f"IMPAC: {impac_private_dict[key]}")
                # print(set_diff)
                private_element_dictionary.update(impac_private_dict)
            datadict.add_private_dict_entries(private_creator, private_element_dictionary)
            print(f"Added private dictionary for {private_creator}")
        except:
            print(f"{private_creator} failed private dict addition")

    # json_ready_impac_dict = jsonify_pydicom_private_dict_list([{"IMPAC": impac_private_dict}])
    converted_list_of_private_dicts = list()
    for creator in converted_dict_of_privates.keys():
        converted_list_of_private_dicts.append({creator: converted_dict_of_privates[creator]})
    json_ready_merged_list_of_dicts = jsonify_pydicom_private_dict_list(converted_list_of_private_dicts)
    with open("merged_privates.json", "wt") as f:
        json_string = json.dumps(json_ready_merged_list_of_dicts)
        f.write(json_string)
        f.flush()
        f.close()
    with open("new_privates_fragment.py", "wt") as g:
        python_string = generate_python_code_from_private_dict_list(converted_list_of_private_dicts)
        g.write(python_string)
        g.flush()
        g.close()
