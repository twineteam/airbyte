import base64
import csv
import json
import os
import xml.etree.ElementTree as ET
from typing import Callable, Dict, List, Optional, Union

import requests
import xmltodict

CURRENT_DIR: str = os.path.dirname(os.path.realpath(__file__))
XML_DIR: str = CURRENT_DIR.replace("utils", "xml")


class WorkdayRequest:
    def __init__(self, base_path: str = XML_DIR) -> None:
        self.base_path: str = base_path
        self.base_template: str = self.read_xml_file("base.xml")
        self.header_template: str = self.read_xml_file("header.xml")

        self.stream_mappings: Dict[str, Dict[str, Union[str, Callable]]] = {
            "workers": {
                "request_file": "workers.xml",
                "parse_response": self.parse_workers_response,
            },
            "worker_details": {
                "request_file": "worker_details.xml",
                "parse_response": self.parse_worker_details_response,
            },
            "worker_details_history": {
                "request_file": "worker_details_history.xml",
                "parse_response": self.parse_worker_details_response,  # Same as worker_details
            },
            "worker_details_photo": {
                "request_file": "worker_details_photo.xml",
                "parse_response": self.parse_worker_details_photo_response,
            },
            "organization_hierarchies": {
                "request_file": "organization_hierarchies.xml",
                "parse_response": self.parse_organization_hierarchies_response,
            },
            "ethnicities": {
                "request_file": "ethnicities.xml",
                "parse_response": self.parse_ethnicities_response,
            },
            "gender_identities": {
                "request_file": "gender_identities.xml",
                "parse_response": self.parse_gender_identities_response,
            },
            "locations": {
                "request_file": "locations.xml",
                "parse_response": self.parse_locations_response,
            },
            "job_profiles": {
                "request_file": "job_profiles.xml",
                "parse_response": self.parse_job_profiles_response,
            },
            "positions": {
                "request_file": "positions.xml",
                "parse_response": self.parse_positions_response,
            },
            "sexual_orientations": {
                "request_file": "sexual_orientations.xml",
                "parse_response": self.parse_sexual_orientations_response,
            },
            "references": {
                "request_file": "references.xml",
                "parse_response": self.parse_references_response,
            },
            "base_snapshot_report": {
                "parse_response": self.parse_base_snapshot_report_response,
            },
            "base_historical_report_compensation": {
                "parse_response": self.parse_base_historical_report_compensation_response,
            },
            "base_historical_report_job": {
                "parse_response": self.parse_base_historical_report_job_response,
            },
        }

    xmlns = r"{urn:com.workday/bsvc}"

    def read_xml_file(self, filename: str) -> str:
        """
        Reads the contents of an XML file.

        Args:
            filename (str): The name of the file to read.

        Returns:
            str: The contents of the file.
        """
        with open(os.path.join(self.base_path, filename), "r") as file:
            return file.read()

    @staticmethod
    def get_namespaces(element: ET.Element) -> Dict[str, str]:
        """
        Extracts the namespaces from an XML element.

        Args:
            element (ET.Element): The XML element to extract namespaces from.

        Returns:
            Dict[str, str]: A dictionary of namespace prefixes and URIs.
        """
        namespaces = {}
        for ns in element.iter():
            if ns.tag.startswith("{"):
                uri, _ = ns.tag[1:].split("}")
                namespaces[uri] = uri
        return {"wd": list(namespaces.keys())[0]}

    @staticmethod
    def safe_find_text(element: ET.Element, tag: str, namespaces: Dict[str, str]) -> str:
        """
        Safely finds and returns the text content of an XML element.

        Args:
            element (ET.Element): The XML element to search within.
            tag (str): The tag name of the element to find.
            namespaces (Dict[str, str]): A dictionary of XML namespace prefixes and URIs.

        Returns:
            str: The text content of the found element, or None if the element or tag is not found.

        """
        if element is None:
            return None

        found_element = element.find(tag, namespaces)
        if found_element is None:
            return None

        return found_element.text

    @staticmethod
    def safe_get_attrib(element: ET.Element, attrib: str) -> str:
        """
        Safely finds and returns the value of an XML element attribute.

        Args:
            element (ET.Element): The XML element to search within.
            attrib (str): The attribute name to find.

        Returns:
            str: The value of the found attribute, or None if the element or attribute is not found.

        """
        if element is None:
            return None

        return element.attrib.get(attrib)

    @staticmethod
    def clean_json_string(json_string: str) -> str:
        """
        Cleans a JSON string by conforming xml attributes to expected format and prepended chars.

        Args:
            json_string (str): The JSON string to clean.

        Returns:
            str: The cleaned JSON string.
        """
        char_replacement_map = {
            "ns0:": "",
            '"@type"': '"-type"',
            '"@Type"': '"-Type"',
            '"@Descriptor"': '"-Descriptor"',
            '"@System_ID"': '"-System_ID"',
            '"@Effective_Date"': '"-Effective_Date"',
            '"@Last_Modified"': '"-Last_Modified"',
            '"@Public"': '"-Public"',
            '"@Primary"': '"-Primary"',
            '"@Is_Legal"': '"-Is_Legal"',
            '"@Is_Preferred"': '"-Is_Preferred"',
            '"#text"': '"#content"',
        }

        for old_char, new_char in char_replacement_map.items():
            json_string = json_string.replace(old_char, new_char)

        return json_string

    def construct_request_body(
        self,
        file_name: str,
        tenant: str,
        username: str,
        password: str,
        per_page: int,
        page: int,
        **kwargs,
    ) -> str:

        specific_xml_content: str = self.read_xml_file(file_name)
        if "PAGE_NUMBER" in specific_xml_content:
            specific_xml_content = specific_xml_content.replace("PAGE_NUMBER", str(page))
        if "PER_PAGE" in specific_xml_content:
            specific_xml_content = specific_xml_content.replace("PER_PAGE", str(per_page))
        if "WORKER_ID" in specific_xml_content:
            assert "worker_id" in kwargs, "worker_id is required for this request"
            worker_id = kwargs.get("worker_id", "")
            specific_xml_content = specific_xml_content.replace("WORKER_ID", worker_id)
        if "AS_OF_EFFECTIVE_DATE" in specific_xml_content:
            as_of_effective_date = kwargs.get("as_of_effective_date", "")
            specific_xml_content = specific_xml_content.replace("AS_OF_EFFECTIVE_DATE", as_of_effective_date)
        if "REFERENCE_SUBCATEGORY_TYPE" in specific_xml_content:
            reference_subcategory_type = kwargs.get("reference_subcategory_type", "")
            specific_xml_content = specific_xml_content.replace(
                "REFERENCE_SUBCATEGORY_TYPE", reference_subcategory_type
            )

        header_content: str = self.header_template % (f"{username}@{tenant}", password)
        full_xml: str = self.base_template % (header_content, specific_xml_content)

        return full_xml

    def parse_response(self, response: requests.Response, stream_name) -> list:
        if response.status_code != 200:
            raise requests.exceptions.HTTPError(f"Request failed with status code {response.status_code}.")

        custom_parse_response_function = self.stream_mappings[stream_name].get("parse_response")

        try:
            xml_data = response.text
            root = ET.fromstring(xml_data)

            namespaces = {"env": "http://schemas.xmlsoap.org/soap/envelope/", "wd": "urn:com.workday/bsvc"}

            response_data = root.find(".//{urn:com.workday/bsvc}Response_Data", namespaces)

            if response_data is None:
                return custom_parse_response_function(response)

            return custom_parse_response_function(response_data, namespaces)

        except Exception as e:
            return custom_parse_response_function(response)

    def parse_workers_response(
        self, response_data: ET.Element, namespaces: Dict[str, str]
    ) -> List[Dict[str, Optional[Union[str, List[Dict[str, str]]]]]]:

        workers: List[Dict[str, Optional[Union[str, List[Dict[str, str]]]]]] = []
        for worker in response_data.findall("{urn:com.workday/bsvc}Worker", namespaces):
            # Parse XML data into JSON
            xml_input = ET.tostring(worker)
            o = xmltodict.parse(xml_input=xml_input)

            # Remove namespace prefix from keys
            cleaned_json_string = self.clean_json_string(json.dumps(o))
            json_data = json.loads(cleaned_json_string)
            worker_data = json_data.get("Worker")

            if worker_data is not None:
                original_hire_date = self.safe_find_text(
                    worker,
                    "{urn:com.workday/bsvc}Worker_Data/{urn:com.workday/bsvc}Employment_Data/{urn:com.workday/bsvc}Worker_Status_Data/{urn:com.workday/bsvc}Original_Hire_Date",
                    namespaces,
                )
                hire_date = self.safe_find_text(
                    worker,
                    "{urn:com.workday/bsvc}Worker_Data/{urn:com.workday/bsvc}Employment_Data/{urn:com.workday/bsvc}Worker_Status_Data/{urn:com.workday/bsvc}Hire_Date",
                    namespaces,
                )
                termination_date = self.safe_find_text(
                    worker,
                    "{urn:com.workday/bsvc}Worker_Data/{urn:com.workday/bsvc}Employment_Data/{urn:com.workday/bsvc}Worker_Status_Data/{urn:com.workday/bsvc}Termination_Date",
                    namespaces,
                )

                worker_data["Original_Hire_Date"] = original_hire_date
                worker_data["Hire_Date"] = hire_date
                worker_data["Termination_Date"] = termination_date

                del worker_data["Worker_Data"]["Employment_Data"]
                workers.append(worker_data)

        return workers

    def parse_worker_details_response(
        self, response_data: ET.Element, namespaces: Dict[str, str]
    ) -> List[Dict[str, Optional[Union[str, List[Dict[str, str]]]]]]:
        worker_details: List[Dict[str, Optional[Union[str, List[Dict[str, str]]]]]] = []
        worker_elem = response_data.find("{urn:com.workday/bsvc}Worker", namespaces)

        if worker_elem is None:
            return worker_details

        # Parse XML data into JSON
        xml_input = ET.tostring(worker_elem)
        o = xmltodict.parse(xml_input=xml_input)

        # Remove namespace prefix from keys
        cleaned_json_string = self.clean_json_string(json.dumps(o))
        json_data = json.loads(cleaned_json_string)
        worker_data = json_data.get("Worker")

        if worker_data is not None:
            worker_details.append(worker_data)

        return worker_details

    def parse_worker_details_photo_response(
        self, response_data: ET.Element, namespaces: Dict[str, str]
    ) -> List[Dict[str, Optional[Union[str, List[Dict[str, str]]]]]]:
        worker_details_photo: List[Dict[str, Optional[Union[str, List[Dict[str, str]]]]]] = []

        worker_elem = response_data.find("{urn:com.workday/bsvc}Worker", namespaces)

        if worker_elem is None:
            return worker_details_photo

        worker_reference_elem = worker_elem.find("{urn:com.workday/bsvc}Worker_Reference", namespaces)
        worker_reference = {
            "ID": [
                {
                    "#content": id_elem.text if id_elem is not None else "Unknown ID",
                    "-type": id_elem.attrib.get("{urn:com.workday/bsvc}type", "Unknown Type"),
                }
                for id_elem in worker_reference_elem.findall("{urn:com.workday/bsvc}ID", namespaces)
            ]
        }

        worker_data_elem = worker_elem.find("{urn:com.workday/bsvc}Worker_Data", namespaces)
        if worker_data_elem is None:
            return worker_details_photo

        photo_data_elem = worker_data_elem.find("{urn:com.workday/bsvc}Photo_Data", namespaces)
        if photo_data_elem is not None:
            filename = self.safe_find_text(photo_data_elem, "{urn:com.workday/bsvc}Filename", namespaces)
            image_base64 = self.safe_find_text(photo_data_elem, "{urn:com.workday/bsvc}Image", namespaces)

            if filename and image_base64:
                image_data = base64.b64decode(image_base64)
                # TODO - Save photo to s3
                filename = None
                filepath = None

            else:
                filename = None
                filepath = None
        else:
            filename = None
            filepath = None

        worker_data = {
            "Photo_Data": {"Filename": filename, "Image": filepath},
            "User_ID": self.safe_find_text(worker_data_elem, "{urn:com.workday/bsvc}User_ID", namespaces),
            "Worker_ID": self.safe_find_text(worker_data_elem, "{urn:com.workday/bsvc}Worker_ID", namespaces),
        }

        worker_details_photo.append(
            {
                "Worker_Reference": worker_reference,
                "Worker_Data": worker_data,
                "Worker_Descriptor": self.safe_find_text(
                    worker_elem, "{urn:com.workday/bsvc}Worker_Descriptor", namespaces
                ),
            }
        )

        return worker_details_photo

    def parse_organization_hierarchies_response(
        self, response_data: ET.Element, namespaces: Dict[str, str]
    ) -> List[Dict[str, Optional[Union[str, List[Dict[str, str]]]]]]:

        organization_hierarchies: List[Dict[str, Optional[Union[str, List[Dict[str, str]]]]]] = []

        for org in response_data.findall("{urn:com.workday/bsvc}Organization", namespaces):
            # Parse XML data into JSON
            xml_input = ET.tostring(org)
            o = xmltodict.parse(xml_input=xml_input)

            # Remove namespace prefix from keys
            cleaned_json_string = self.clean_json_string(json.dumps(o))
            json_data = json.loads(cleaned_json_string)
            org_data = json_data.get("Organization")

            if org_data is not None:
                organization_hierarchies.append(org_data)

        return organization_hierarchies

    def parse_ethnicities_response(
        self, response_data: ET.Element, namespaces: Dict[str, str]
    ) -> List[Dict[str, Optional[Union[str, List[Dict[str, str]]]]]]:

        ethnicities: List[Dict[str, Optional[Union[str, List[Dict[str, str]]]]]] = []

        if response_data is None:
            return ethnicities

        for ethnicity in response_data.findall("{urn:com.workday/bsvc}Ethnicity", namespaces):
            # Parse XML data into JSON
            xml_input = ET.tostring(ethnicity)
            o = xmltodict.parse(xml_input=xml_input)

            # Remove namespace prefix from keys
            cleaned_json_string = self.clean_json_string(json.dumps(o))
            json_data = json.loads(cleaned_json_string)
            ethnicity_data = json_data.get("Ethnicity")

            if ethnicity_data is not None:
                ethnicities.append(ethnicity_data)

        return ethnicities

    def parse_gender_identities_response(
        self, response_data: ET.Element, namespaces: Dict[str, str]
    ) -> List[Dict[str, Optional[Union[str, List[Dict[str, str]]]]]]:

        gender_identities: List[Dict[str, Optional[Union[str, List[Dict[str, str]]]]]] = []

        if response_data is None:
            return gender_identities

        for gender_identity in response_data.findall("{urn:com.workday/bsvc}Gender_Identity", namespaces):
            # Parse XML data into JSON
            xml_input = ET.tostring(gender_identity)
            o = xmltodict.parse(xml_input=xml_input)

            # Remove namespace prefix from keys
            cleaned_json_string = self.clean_json_string(json.dumps(o))
            json_data = json.loads(cleaned_json_string)
            gender_identity_data = json_data.get("Gender_Identity")

            if gender_identity_data is not None:
                gender_identities.append(gender_identity_data)

        return gender_identities

    def parse_locations_response(
        self, response_data: ET.Element, namespaces: Dict[str, str]
    ) -> List[Dict[str, Optional[Union[str, List[Dict[str, str]]]]]]:
        locations: List[Dict[str, Optional[Union[str, List[Dict[str, str]]]]]] = []

        if response_data is None:
            return locations

        for location in response_data.findall("{urn:com.workday/bsvc}Location", namespaces):
            # Parse XML data into JSON
            xml_input = ET.tostring(location)
            o = xmltodict.parse(xml_input=xml_input)

            # Remove namespace prefix from keys
            cleaned_json_string = self.clean_json_string(json.dumps(o))
            json_data = json.loads(cleaned_json_string)
            location_data = json_data.get("Location")

            if location_data is not None:
                locations.append(location_data)

        return locations

    def parse_job_profiles_response(
        self, response_data: ET.Element, namespaces: Dict[str, str]
    ) -> List[Dict[str, Optional[Union[str, List[Dict[str, str]]]]]]:

        job_profiles: List[Dict[str, Optional[Union[str, List[Dict[str, str]]]]]] = []

        if response_data is None:
            return job_profiles

        for job_profile in response_data.findall("{urn:com.workday/bsvc}Job_Profile", namespaces):
            # Parse XML data into JSON
            xml_input = ET.tostring(job_profile)
            o = xmltodict.parse(xml_input=xml_input)

            # Remove namespace prefix from keys
            cleaned_json_string = self.clean_json_string(json.dumps(o))
            json_data = json.loads(cleaned_json_string)
            job_profile_data = json_data.get("Job_Profile")

            if job_profile_data is not None:
                job_profiles.append(job_profile_data)

        return job_profiles

    def parse_positions_response(
        self, response_data: ET.Element, namespaces: Dict[str, str]
    ) -> List[Dict[str, Optional[Union[str, List[Dict[str, str]]]]]]:

        positions: List[Dict[str, Optional[Union[str, List[Dict[str, str]]]]]] = []

        if response_data is None:
            return positions

        for position in response_data.findall("{urn:com.workday/bsvc}Position", namespaces):
            # Parse XML data into JSON
            xml_input = ET.tostring(position)
            o = xmltodict.parse(xml_input=xml_input)

            # Remove namespace prefix from keys
            cleaned_json_string = self.clean_json_string(json.dumps(o))
            json_data = json.loads(cleaned_json_string)
            position_data = json_data.get("Position")

            if position_data is not None:
                positions.append(position_data)

        return positions

    def parse_sexual_orientations_response(
        self, response_data: ET.Element, namespaces: Dict[str, str]
    ) -> List[Dict[str, Optional[Union[str, List[Dict[str, str]]]]]]:

        sexual_orientations: List[Dict[str, Optional[Union[str, List[Dict[str, str]]]]]] = []

        if response_data is None:
            return sexual_orientations

        for sexual_orientation in response_data.findall("{urn:com.workday/bsvc}Sexual_Orientation", namespaces):
            # Parse XML data into JSON
            xml_input = ET.tostring(sexual_orientation)
            o = xmltodict.parse(xml_input=xml_input)

            # Remove namespace prefix from keys
            cleaned_json_string = self.clean_json_string(json.dumps(o))
            json_data = json.loads(cleaned_json_string)
            sexual_orientation_data = json_data.get("Sexual_Orientation")

            if sexual_orientation_data is not None:
                sexual_orientations.append(sexual_orientation_data)

        return sexual_orientations

    def parse_references_response(
        self, response_data: ET.Element, namespaces: Dict[str, str]
    ) -> List[Dict[str, Optional[Union[str, List[Dict[str, str]]]]]]:

        references: List[Dict[str, Optional[Union[str, List[Dict[str, str]]]]]] = []

        if response_data is None:
            return references

        for reference in response_data.findall("{urn:com.workday/bsvc}Reference_ID", namespaces):
            reference_descriptor = reference.attrib.get("{urn:com.workday/bsvc}Descriptor")
            reference_id_reference_elem = reference.find("{urn:com.workday/bsvc}Reference_ID_Reference", namespaces)
            reference_id_data_elem = reference.find("{urn:com.workday/bsvc}Reference_ID_Data", namespaces)

            reference_id_reference = (
                {
                    "ID": [
                        {
                            "#content": id_elem.text if id_elem is not None else "Unknown ID",
                            "-type": id_elem.attrib.get("{urn:com.workday/bsvc}type", "Unknown Type"),
                        }
                        for id_elem in reference_id_reference_elem.findall("{urn:com.workday/bsvc}ID", namespaces)
                    ]
                }
                if reference_id_reference_elem is not None
                else None
            )

            reference_id_data = (
                {
                    "ID": self.safe_find_text(reference_id_data_elem, "{urn:com.workday/bsvc}ID", namespaces),
                    "Reference_ID_Type": self.safe_find_text(
                        reference_id_data_elem, "{urn:com.workday/bsvc}Reference_ID_Type", namespaces
                    ),
                    "Referenced_Object_Descriptor": self.safe_find_text(
                        reference_id_data_elem, "{urn:com.workday/bsvc}Referenced_Object_Descriptor", namespaces
                    ),
                }
                if reference_id_data_elem is not None
                else None
            )

            references.append(
                {
                    "-Descriptor": reference_descriptor,
                    "Reference_ID_Reference": reference_id_reference,
                    "Reference_ID_Data": reference_id_data,
                }
            )

        return references

    def parse_base_snapshot_report_response(
        self, response: requests.Response
    ) -> List[Dict[str, Optional[Union[str, List[Dict[str, str]]]]]]:
        response_csv = response.content.decode("utf-8")
        reader = csv.DictReader(response_csv.splitlines())

        return [row for row in reader]

    def parse_base_historical_report_compensation_response(
        self, response: requests.Response
    ) -> List[Dict[str, Optional[Union[str, List[Dict[str, str]]]]]]:

        xml_data = response.text
        root = ET.fromstring(xml_data)

        namespaces = self.get_namespaces(root)
        namespace_tag = namespaces["wd"]

        main_compensation_tag = ""
        sub_compensation_tag = ""

        # Tags can vary depending on the way the Workday integration was setup
        if (
            "Compensation_History_-_Previous_System_group" in xml_data
            and "Compensation_History_Record_from_Previous_System" in xml_data
        ):
            main_compensation_tag = "Compensation_History_-_Previous_System_group"
            sub_compensation_tag = "Compensation_History_Record_from_Previous_System"
        elif (
            "Job_History_from_Previous_System_group" in xml_data
            and "Job_Position_History_Record_from_Previous_System" in xml_data
        ):
            main_compensation_tag = "Job_History_from_Previous_System_group"
            sub_compensation_tag = "Job_Position_History_Record_from_Previous_System"

        compensation_records: List[Dict[str, Optional[Union[str, List[Dict[str, str]]]]]] = []

        for report_entry in root.findall(f".//{{{namespace_tag}}}Report_Entry", namespaces):
            employee_id = self.safe_find_text(report_entry, f"{{{namespace_tag}}}Employee_ID", namespaces)
            worker_elem = report_entry.find(f"{{{namespace_tag}}}Worker", namespaces)
            worker_descriptor = (
                worker_elem.attrib.get(f"{{{namespace_tag}}}Descriptor") if worker_elem is not None else None
            )
            worker_ids = (
                [
                    {"-type": id_elem.attrib.get(f"{{{namespace_tag}}}type"), "#content": id_elem.text}
                    for id_elem in worker_elem.findall(f"{{{namespace_tag}}}ID", namespaces)
                ]
                if worker_elem is not None
                else []
            )

            compensation_history = []
            for history_elem in report_entry.findall(f"{{{namespace_tag}}}{main_compensation_tag}", namespaces):
                compensation_history_entry_elem = history_elem.find(
                    f"{{{namespace_tag}}}{sub_compensation_tag}", namespaces
                )
                currency_elem = history_elem.find(f"{{{namespace_tag}}}Currency", namespaces)
                frequency_elem = history_elem.find(f"{{{namespace_tag}}}Frequency", namespaces)

                compensation_history_item = {
                    "Worker_History_Name": self.safe_find_text(
                        history_elem, f"{{{namespace_tag}}}Worker_History_Name", namespaces
                    ),
                    "Effective_Date": self.safe_find_text(
                        history_elem, f"{{{namespace_tag}}}Effective_Date", namespaces
                    ),
                    "Reason": self.safe_find_text(history_elem, f"{{{namespace_tag}}}Reason", namespaces),
                    "Amount": self.safe_find_text(history_elem, f"{{{namespace_tag}}}Amount", namespaces),
                    "Amount_Change": self.safe_find_text(history_elem, f"{{{namespace_tag}}}Amount_Change", namespaces),
                }

                if compensation_history_entry_elem is not None:
                    compensation_history_item[sub_compensation_tag] = {
                        "-Descriptor": compensation_history_entry_elem.attrib.get(f"{{{namespace_tag}}}Descriptor"),
                        "ID": [
                            {"-type": id_elem.attrib.get(f"{{{namespace_tag}}}type"), "#content": id_elem.text}
                            for id_elem in compensation_history_entry_elem.findall(f"{{{namespace_tag}}}ID", namespaces)
                        ],
                    }

                if currency_elem is not None:
                    compensation_history_item["Currency"] = {
                        "-Descriptor": currency_elem.attrib.get(f"{{{namespace_tag}}}Descriptor"),
                        "ID": [
                            {"-type": id_elem.attrib.get(f"{{{namespace_tag}}}type"), "#content": id_elem.text}
                            for id_elem in currency_elem.findall(f"{{{namespace_tag}}}ID", namespaces)
                        ],
                    }

                if frequency_elem is not None:
                    compensation_history_item["Frequency"] = {
                        "-Descriptor": frequency_elem.attrib.get(f"{{{namespace_tag}}}Descriptor"),
                        "ID": [
                            {"-type": id_elem.attrib.get(f"{{{namespace_tag}}}type"), "#content": id_elem.text}
                            for id_elem in frequency_elem.findall(f"{{{namespace_tag}}}ID", namespaces)
                        ],
                    }

                compensation_history.append(compensation_history_item)

            record = {"Employee_ID": employee_id, "Worker": {"-Descriptor": worker_descriptor, "ID": worker_ids}}

            if len(compensation_history) > 0:
                record[main_compensation_tag] = compensation_history

            compensation_records.append(record)

        return compensation_records

    def parse_base_historical_report_job_response(
        self, response: requests.Response
    ) -> List[Dict[str, Optional[Union[str, List[Dict[str, str]]]]]]:
        xml_data = response.text
        root = ET.fromstring(xml_data)

        namespaces = self.get_namespaces(root)
        namespace_tag = namespaces["wd"]

        # TODO: Hardcoded for now because only 1 client is using this. Need to make it dynamic in the future
        main_job_tag = "Job_History_from_Previous_System_group"
        sub_job_tag = "History_Record"

        job_records: List[Dict[str, Optional[Union[str, List[Dict[str, str]]]]]] = []

        def get_all_positions_group_data(
            all_positions_group_elem: ET.Element,
        ) -> Dict[str, Optional[Union[str, List[Dict[str, str]]]]]:
            position_elem = all_positions_group_elem.find(f"{{{namespace_tag}}}Position", namespaces)
            position_worker_type_elem = all_positions_group_elem.find(
                f"{{{namespace_tag}}}Position_Worker_Type", namespaces
            )
            time_type_elem = all_positions_group_elem.find(f"{{{namespace_tag}}}Time_Type", namespaces)
            position_manager_elem = all_positions_group_elem.find(f"{{{namespace_tag}}}Position_Manager", namespaces)

            all_positions_group_data = {
                "Business_Title": self.safe_find_text(
                    all_positions_group_elem, f"{{{namespace_tag}}}Business_Title", namespaces
                )
            }

            if position_elem is not None:
                all_positions_group_data["Position"] = {
                    "-Descriptor": position_elem.attrib.get(f"{{{namespace_tag}}}Descriptor"),
                    "ID": {
                        "#content": self.safe_find_text(position_elem, f"{{{namespace_tag}}}ID", namespaces),
                        "-type": position_elem.find(f"{{{namespace_tag}}}ID").attrib.get(f"{{{namespace_tag}}}type"),
                    },
                }

            if position_worker_type_elem is not None:
                all_positions_group_data["Position_Worker_Type"] = {
                    "-Descriptor": position_worker_type_elem.attrib.get(f"{{{namespace_tag}}}Descriptor"),
                    "ID": [
                        {"#content": id_elem.text, "-type": id_elem.attrib.get(f"{{{namespace_tag}}}type")}
                        for id_elem in position_worker_type_elem.findall(f"{{{namespace_tag}}}ID", namespaces)
                    ],
                }

            if time_type_elem is not None:
                all_positions_group_data["Time_Type"] = {
                    "-Descriptor": time_type_elem.attrib.get(f"{{{namespace_tag}}}Descriptor"),
                    "ID": [
                        {"#content": id_elem.text, "-type": id_elem.attrib.get(f"{{{namespace_tag}}}type")}
                        for id_elem in time_type_elem.findall(f"{{{namespace_tag}}}ID", namespaces)
                    ],
                }

            if position_manager_elem is not None:
                all_positions_group_data["Position_Manager"] = {
                    "-Descriptor": position_manager_elem.attrib.get(f"{{{namespace_tag}}}Descriptor"),
                    "ID": [
                        {"#content": id_elem.text, "-type": id_elem.attrib.get(f"{{{namespace_tag}}}type")}
                        for id_elem in position_manager_elem.findall(f"{{{namespace_tag}}}ID", namespaces)
                    ],
                }

            return all_positions_group_data

        for report_entry in root.findall(f".//{{{namespace_tag}}}Report_Entry", namespaces):
            all_positions_group_elems = report_entry.findall(f"{{{namespace_tag}}}All_Positions_group", namespaces)

            if len(all_positions_group_elems) > 1:
                all_positions_group_data = []
                for all_positions_group_elem in all_positions_group_elems:
                    all_positions_group_data.append(get_all_positions_group_data(all_positions_group_elem))

            elif len(all_positions_group_elems) == 1:
                all_positions_group_data = get_all_positions_group_data(all_positions_group_elems[0])

            else:
                all_positions_group_data = None

            employee_id = self.safe_find_text(report_entry, f"{{{namespace_tag}}}Employee_ID", namespaces)
            hire_date = self.safe_find_text(report_entry, f"{{{namespace_tag}}}Hire_Date", namespaces)
            original_hire_date = self.safe_find_text(report_entry, f"{{{namespace_tag}}}Original_Hire_Date", namespaces)
            termination_reason = self.safe_find_text(report_entry, f"{{{namespace_tag}}}Termination_Reason", namespaces)
            termination_date = self.safe_find_text(report_entry, f"{{{namespace_tag}}}termination_date", namespaces)
            termination_regret = self.safe_find_text(report_entry, f"{{{namespace_tag}}}termination_regret", namespaces)
            termination_category_elem = report_entry.find(f"{{{namespace_tag}}}Termination_Category", namespaces)
            termination_category = (
                {
                    "-Descriptor": termination_category_elem.attrib.get(f"{{{namespace_tag}}}Descriptor"),
                    "ID": [
                        {"#content": id_elem.text, "-type": id_elem.attrib.get(f"{{{namespace_tag}}}type")}
                        for id_elem in termination_category_elem.findall(f"{{{namespace_tag}}}ID", namespaces)
                    ],
                }
                if termination_category_elem is not None
                else None
            )

            worker_elem = report_entry.find(f"{{{namespace_tag}}}Worker", namespaces)
            worker = (
                {
                    "-Descriptor": worker_elem.attrib.get(f"{{{namespace_tag}}}Descriptor"),
                    "ID": [
                        {"#content": id_elem.text, "-type": id_elem.attrib.get(f"{{{namespace_tag}}}type")}
                        for id_elem in worker_elem.findall(f"{{{namespace_tag}}}ID", namespaces)
                    ],
                }
                if worker_elem is not None
                else None
            )

            job_history = []
            for history_elem in report_entry.findall(f"{{{namespace_tag}}}{main_job_tag}", namespaces):
                job_history_entry_elem = history_elem.find(f"{{{namespace_tag}}}{sub_job_tag}", namespaces)

                job_history_item = {
                    "Compensation": self.safe_find_text(history_elem, f"{{{namespace_tag}}}Compensation", namespaces),
                    "Department": self.safe_find_text(history_elem, f"{{{namespace_tag}}}Department", namespaces),
                    "Effective_Date": self.safe_find_text(
                        history_elem, f"{{{namespace_tag}}}Effective_Date", namespaces
                    ),
                    "Function": self.safe_find_text(history_elem, f"{{{namespace_tag}}}Function", namespaces),
                    "Hourly_Salaried": self.safe_find_text(
                        history_elem, f"{{{namespace_tag}}}Hourly_Salaried", namespaces
                    ),
                    "Job_Title": self.safe_find_text(history_elem, f"{{{namespace_tag}}}Job_Title", namespaces),
                    "Location": self.safe_find_text(history_elem, f"{{{namespace_tag}}}Location", namespaces),
                    "Manager": self.safe_find_text(history_elem, f"{{{namespace_tag}}}Manager", namespaces),
                    "Reason": self.safe_find_text(history_elem, f"{{{namespace_tag}}}Reason", namespaces),
                    "Salary_Grade": self.safe_find_text(history_elem, f"{{{namespace_tag}}}Salary_Grade", namespaces),
                    "Worker_History_Name": self.safe_find_text(
                        history_elem, f"{{{namespace_tag}}}Worker_History_Name", namespaces
                    ),
                }

                if job_history_entry_elem is not None:
                    job_history_item[sub_job_tag] = {
                        "-Descriptor": job_history_entry_elem.attrib.get(f"{{{namespace_tag}}}Descriptor"),
                        "ID": [
                            {"#content": id_elem.text, "-type": id_elem.attrib.get(f"{{{namespace_tag}}}type")}
                            for id_elem in job_history_entry_elem.findall(f"{{{namespace_tag}}}ID", namespaces)
                        ],
                    }

                job_history.append(job_history_item)

            record = {
                "Employee_ID": employee_id,
                "All_Positions_group": all_positions_group_data,
                "Hire_Date": hire_date,
                "Original_Hire_Date": original_hire_date,
                "Termination_Reason": termination_reason,
                "termination_date": termination_date,
                "termination_regret": termination_regret,
                "Termination_Category": termination_category,
                "Worker": worker,
                main_job_tag: job_history,
            }

            job_records.append(record)

        return job_records
