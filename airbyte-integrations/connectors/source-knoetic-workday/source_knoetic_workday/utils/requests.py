import os
import xml.etree.ElementTree as ET
from typing import Callable, Dict, List, Optional, Union

import requests

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
            }
        }

    def read_xml_file(self, filename: str) -> str:
        with open(os.path.join(self.base_path, filename), "r") as file:
            return file.read()

    def construct_request_body(
        self,
        file_name: str,
        tenant: str,
        username: str,
        password: str,
        page: int,
        per_page: int = 200,
    ) -> str:
        specific_xml_content: str = self.read_xml_file(file_name)
        if "PAGE_NUMBER" in specific_xml_content:
            specific_xml_content = specific_xml_content.replace("PAGE_NUMBER", str(page))
        if "PER_PAGE" in specific_xml_content:
            specific_xml_content = specific_xml_content.replace("PER_PAGE", str(per_page))

        header_content: str = self.header_template % (f"{username}@{tenant}", password)
        full_xml: str = self.base_template % (header_content, specific_xml_content)

        return full_xml

    def parse_response(self, response: requests.Response, stream_name) -> list:
        if response.status_code != 200:
            raise requests.exceptions.HTTPError(f"Request failed with status code {response.status_code}.")

        xml_data = response.text
        root = ET.fromstring(xml_data)

        namespaces = {"env": "http://schemas.xmlsoap.org/soap/envelope/", "wd": "urn:com.workday/bsvc"}

        response_data = root.find(".//{urn:com.workday/bsvc}Response_Data", namespaces)

        custom_parse_response_function = self.stream_mappings[stream_name].get("parse_response")
        return custom_parse_response_function(response_data, namespaces)

    def parse_workers_response(
        self, response_data: ET.Element, namespaces: Dict[str, str]
    ) -> List[Dict[str, Optional[Union[str | None, List[Dict[str, str]]]]]]:

        workers: List[Dict[str, Optional[Union[str | None, List[Dict[str, str]]]]]] = []

        if response_data is None:
            return workers

        for worker in response_data.findall("{urn:com.workday/bsvc}Worker", namespaces):
            worker_descriptor_elem = worker.find("{urn:com.workday/bsvc}Worker_Descriptor", namespaces)
            worker_descriptor = worker_descriptor_elem.text if worker_descriptor_elem is not None else None

            worker_data: Dict[str, Union[str | None, List[Dict[str, str]]]] = {
                "Worker_Descriptor": worker_descriptor,
                "Worker_Reference": [],
            }
            for id_elem in worker.findall(
                ".//{urn:com.workday/bsvc}Worker_Reference/{urn:com.workday/bsvc}ID", namespaces
            ):
                if id_elem is not None:
                    worker_data["Worker_Reference"].append(
                        {
                            "type": id_elem.attrib.get("{urn:com.workday/bsvc}type", "Unknown Type"),
                            "value": id_elem.text if id_elem.text is not None else "Unknown ID",
                        }
                    )
            workers.append(worker_data)

        return workers

    def parse_organization_hierarchies_response(
        self, response_data: ET.Element, namespaces: Dict[str, str]
    ) -> List[Dict[str, Optional[Union[str | None, List[Dict[str, str]]]]]]:

        organization_hierarchies: List[Dict[str, Optional[Union[str | None, List[Dict[str, str]]]]]] = []

        if response_data is None:
            return organization_hierarchies

        for org in response_data.findall("{urn:com.workday/bsvc}Organization", namespaces):
            org_reference_elem = org.find("{urn:com.workday/bsvc}Organization_Reference", namespaces)
            org_data_elem = org.find("{urn:com.workday/bsvc}Organization_Data", namespaces)

            org_reference = {
                "ID": [
                    {
                        "#content": id_elem.text if id_elem is not None else "Unknown ID",
                        "-type": id_elem.attrib.get("{urn:com.workday/bsvc}type", "Unknown Type"),
                    }
                    for id_elem in org_reference_elem.findall("{urn:com.workday/bsvc}ID", namespaces)
                ]
            }

            org_data = {
                "Reference_ID": (
                    org_data_elem.find("{urn:com.workday/bsvc}Reference_ID", namespaces).text
                    if org_data_elem.find("{urn:com.workday/bsvc}Reference_ID", namespaces) is not None
                    else None
                ),
                "Name": (
                    org_data_elem.find("{urn:com.workday/bsvc}Name", namespaces).text
                    if org_data_elem.find("{urn:com.workday/bsvc}Name", namespaces) is not None
                    else None
                ),
                "Availibility_Date": (
                    org_data_elem.find("{urn:com.workday/bsvc}Availibility_Date", namespaces).text
                    if org_data_elem.find("{urn:com.workday/bsvc}Availibility_Date", namespaces) is not None
                    else None
                ),
                "Last_Updated_DateTime": (
                    org_data_elem.find("{urn:com.workday/bsvc}Last_Updated_DateTime", namespaces).text
                    if org_data_elem.find("{urn:com.workday/bsvc}Last_Updated_DateTime", namespaces) is not None
                    else None
                ),
                "Inactive": (
                    org_data_elem.find("{urn:com.workday/bsvc}Inactive", namespaces).text
                    if org_data_elem.find("{urn:com.workday/bsvc}Inactive", namespaces) is not None
                    else None
                ),
                "Include_Manager_in_Name": (
                    org_data_elem.find("{urn:com.workday/bsvc}Include_Manager_in_Name", namespaces).text
                    if org_data_elem.find("{urn:com.workday/bsvc}Include_Manager_in_Name", namespaces) is not None
                    else None
                ),
                "Include_Organization_Code_in_Name": (
                    org_data_elem.find("{urn:com.workday/bsvc}Include_Organization_Code_in_Name", namespaces).text
                    if org_data_elem.find("{urn:com.workday/bsvc}Include_Organization_Code_in_Name", namespaces)
                    is not None
                    else None
                ),
                "Organization_Type_Reference": {
                    "ID": (
                        [
                            {
                                "#content": id_elem.text if id_elem is not None else "Unknown ID",
                                "-type": id_elem.attrib.get("{urn:com.workday/bsvc}type", "Unknown Type"),
                            }
                            for id_elem in org_data_elem.find(
                                "{urn:com.workday/bsvc}Organization_Type_Reference", namespaces
                            ).findall("{urn:com.workday/bsvc}ID", namespaces)
                        ]
                        if org_data_elem.find("{urn:com.workday/bsvc}Organization_Type_Reference", namespaces)
                        is not None
                        else []
                    )
                },
                "Organization_Subtype_Reference": {
                    "ID": (
                        [
                            {
                                "#content": id_elem.text if id_elem is not None else "Unknown ID",
                                "-type": id_elem.attrib.get("{urn:com.workday/bsvc}type", "Unknown Type"),
                            }
                            for id_elem in org_data_elem.find(
                                "{urn:com.workday/bsvc}Organization_Subtype_Reference", namespaces
                            ).findall("{urn:com.workday/bsvc}ID", namespaces)
                        ]
                        if org_data_elem.find("{urn:com.workday/bsvc}Organization_Subtype_Reference", namespaces)
                        is not None
                        else []
                    )
                },
                "Organization_Visibility_Reference": {
                    "ID": (
                        [
                            {
                                "#content": id_elem.text if id_elem is not None else "Unknown ID",
                                "-type": id_elem.attrib.get("{urn:com.workday/bsvc}type", "Unknown Type"),
                            }
                            for id_elem in org_data_elem.find(
                                "{urn:com.workday/bsvc}Organization_Visibility_Reference", namespaces
                            ).findall("{urn:com.workday/bsvc}ID", namespaces)
                        ]
                        if org_data_elem.find("{urn:com.workday/bsvc}Organization_Visibility_Reference", namespaces)
                        is not None
                        else []
                    )
                },
                "External_IDs_Data": {
                    "ID": (
                        [
                            {
                                "#content": id_elem.text if id_elem is not None else "Unknown ID",
                                "-System_ID": id_elem.attrib.get(
                                    "{urn:com.workday/bsvc}System_ID", "Unknown System ID"
                                ),
                            }
                            for id_elem in org_data_elem.find(
                                "{urn:com.workday/bsvc}External_IDs_Data", namespaces
                            ).findall("{urn:com.workday/bsvc}ID", namespaces)
                        ]
                        if org_data_elem.find("{urn:com.workday/bsvc}External_IDs_Data", namespaces) is not None
                        else []
                    )
                },
                "Hierarchy_Data": {
                    "Top-Level_Organization_Reference": {
                        "ID": (
                            [
                                {
                                    "#content": id_elem.text if id_elem is not None else "Unknown ID",
                                    "-type": id_elem.attrib.get("{urn:com.workday/bsvc}type", "Unknown Type"),
                                }
                                for id_elem in org_data_elem.find(
                                    "{urn:com.workday/bsvc}Hierarchy_Data/{urn:com.workday/bsvc}Top-Level_Organization_Reference",
                                    namespaces,
                                ).findall("{urn:com.workday/bsvc}ID", namespaces)
                            ]
                            if org_data_elem.find(
                                "{urn:com.workday/bsvc}Hierarchy_Data/{urn:com.workday/bsvc}Top-Level_Organization_Reference",
                                namespaces,
                            )
                            is not None
                            else []
                        )
                    }
                },
            }

            organization_hierarchies.append(
                {
                    "Organization_Reference": org_reference,
                    "Organization_Data": org_data,
                }
            )

        return organization_hierarchies

    def parse_ethnicities_response(
        self,
        response_data: ET.Element,
        namespaces: Dict[str, str]
    ) -> List[Dict[str, Optional[Union[str | None, List[Dict[str, str]]]]]]:

        ethnicities: List[Dict[str, Optional[Union[str | None, List[Dict[str, str]]]]]] = []

        if response_data is None:
            return ethnicities

        for ethnicity in response_data.findall("{urn:com.workday/bsvc}Ethnicity", namespaces):
            ethnicity_reference_elem = ethnicity.find("{urn:com.workday/bsvc}Ethnicity_Reference", namespaces)
            ethnicity_data_elem = ethnicity.find("{urn:com.workday/bsvc}Ethnicity_Data", namespaces)

            ethnicity_reference = {
                "ID": [
                    {
                        "#content": id_elem.text if id_elem is not None else "Unknown ID",
                        "-type": id_elem.attrib.get("{urn:com.workday/bsvc}type", "Unknown Type")
                    }
                    for id_elem in ethnicity_reference_elem.findall("{urn:com.workday/bsvc}ID", namespaces)
                ]
            }

            location_reference = {
                "ID": [
                    {
                        "#content": id_elem.text if id_elem is not None else "Unknown ID",
                        "-type": id_elem.attrib.get("{urn:com.workday/bsvc}type", "Unknown Type")
                    }
                    for id_elem in ethnicity_data_elem.find("{urn:com.workday/bsvc}Location_Reference", namespaces).findall("{urn:com.workday/bsvc}ID", namespaces)
                ] if ethnicity_data_elem.find("{urn:com.workday/bsvc}Location_Reference", namespaces) is not None else []
            }

            ethnicity_mapping_reference = {
                "ID": [
                    {
                        "#content": id_elem.text if id_elem is not None else "Unknown ID",
                        "-type": id_elem.attrib.get("{urn:com.workday/bsvc}type", "Unknown Type")
                    }
                    for id_elem in ethnicity_data_elem.find("{urn:com.workday/bsvc}Ethnicity_Mapping_Reference", namespaces).findall("{urn:com.workday/bsvc}ID", namespaces)
                ] if ethnicity_data_elem.find("{urn:com.workday/bsvc}Ethnicity_Mapping_Reference", namespaces) is not None else []
            }

            ethnicity_data = {
                "ID": ethnicity_data_elem.find("{urn:com.workday/bsvc}ID", namespaces).text if ethnicity_data_elem.find("{urn:com.workday/bsvc}ID", namespaces) is not None else None,
                "Name": ethnicity_data_elem.find("{urn:com.workday/bsvc}Name", namespaces).text if ethnicity_data_elem.find("{urn:com.workday/bsvc}Name", namespaces) is not None else None,
                "Description": ethnicity_data_elem.find("{urn:com.workday/bsvc}Description", namespaces).text if ethnicity_data_elem.find("{urn:com.workday/bsvc}Description", namespaces) is not None else None,
                "Location_Reference": location_reference,
                "Ethnicity_Mapping_Reference": ethnicity_mapping_reference,
                "Inactive": ethnicity_data_elem.find("{urn:com.workday/bsvc}Inactive", namespaces).text if ethnicity_data_elem.find("{urn:com.workday/bsvc}Inactive", namespaces) is not None else None
            }

            ethnicities.append({
                "Ethnicity_Reference": ethnicity_reference,
                "Ethnicity_Data": ethnicity_data
            })

        return ethnicities
    
    def parse_gender_identities_response(
    self,
    response_data: ET.Element,
    namespaces: Dict[str, str]
    ) -> List[Dict[str, Optional[Union[str | None, List[Dict[str, str]]]]]]:

        gender_identities: List[Dict[str, Optional[Union[str | None, List[Dict[str, str]]]]]] = []

        if response_data is None:
            return gender_identities

        for gender_identity in response_data.findall("{urn:com.workday/bsvc}Gender_Identity", namespaces):
            gender_identity_reference_elem = gender_identity.find("{urn:com.workday/bsvc}Gender_Identity_Reference", namespaces)
            gender_identity_data_elem = gender_identity.find("{urn:com.workday/bsvc}Gender_Identity_Data", namespaces)

            gender_identity_reference = {
                "ID": [
                    {
                        "#content": id_elem.text if id_elem is not None else "Unknown ID",
                        "-type": id_elem.attrib.get("{urn:com.workday/bsvc}type", "Unknown Type")
                    }
                    for id_elem in gender_identity_reference_elem.findall("{urn:com.workday/bsvc}ID", namespaces)
                ]
            }

            gender_identity_data = {
                "ID": gender_identity_data_elem.find("{urn:com.workday/bsvc}ID", namespaces).text if gender_identity_data_elem.find("{urn:com.workday/bsvc}ID", namespaces) is not None else None,
                "Gender_Identity_Name": gender_identity_data_elem.find("{urn:com.workday/bsvc}Gender_Identity_Name", namespaces).text if gender_identity_data_elem.find("{urn:com.workday/bsvc}Gender_Identity_Name", namespaces) is not None else None,
                "Gender_Identity_Code": gender_identity_data_elem.find("{urn:com.workday/bsvc}Gender_Identity_Code", namespaces).text if gender_identity_data_elem.find("{urn:com.workday/bsvc}Gender_Identity_Code", namespaces) is not None else None,
                "Gender_Identity_Inactive": gender_identity_data_elem.find("{urn:com.workday/bsvc}Gender_Identity_Inactive", namespaces).text if gender_identity_data_elem.find("{urn:com.workday/bsvc}Gender_Identity_Inactive", namespaces) is not None else None
            }

            gender_identities.append({
                "Gender_Identity_Reference": gender_identity_reference,
                "Gender_Identity_Data": gender_identity_data
            })

        return gender_identities

    def parse_locations_response(
        self,
        response_data: ET.Element,
        namespaces: Dict[str, str]
    ) -> List[Dict[str, Optional[Union[str | None, List[Dict[str, str]]]]]]:
        locations: List[Dict[str, Optional[Union[str | None, List[Dict[str, str]]]]]] = []

        if response_data is None:
            return locations

        for location in response_data.findall("{urn:com.workday/bsvc}Location", namespaces):
            location_reference_elem = location.find("{urn:com.workday/bsvc}Location_Reference", namespaces)
            location_data_elem = location.find("{urn:com.workday/bsvc}Location_Data", namespaces)

            location_reference = {
                "ID": [
                    {
                        "#content": id_elem.text if id_elem is not None else "Unknown ID",
                        "-type": id_elem.attrib.get("{urn:com.workday/bsvc}type", "Unknown Type")
                    }
                    for id_elem in location_reference_elem.findall("{urn:com.workday/bsvc}ID", namespaces)
                ]
            }

            location_usage_reference = {
                "ID": [
                    {
                        "#content": id_elem.text if id_elem is not None else "Unknown ID",
                        "-type": id_elem.attrib.get("{urn:com.workday/bsvc}type", "Unknown Type")
                    }
                    for id_elem in location_data_elem.find("{urn:com.workday/bsvc}Location_Usage_Reference", namespaces).findall("{urn:com.workday/bsvc}ID", namespaces)
                ] if location_data_elem.find("{urn:com.workday/bsvc}Location_Usage_Reference", namespaces) is not None else []
            }

            location_type_reference = {
                "ID": [
                    {
                        "#content": id_elem.text if id_elem is not None else "Unknown ID",
                        "-type": id_elem.attrib.get("{urn:com.workday/bsvc}type", "Unknown Type")
                    }
                    for id_elem in location_data_elem.find("{urn:com.workday/bsvc}Location_Type_Reference", namespaces).findall("{urn:com.workday/bsvc}ID", namespaces)
                ] if location_data_elem.find("{urn:com.workday/bsvc}Location_Type_Reference", namespaces) is not None else []
            }

            location_hierarchy_reference = {
                "ID": [
                    {
                        "#content": id_elem.text if id_elem is not None else "Unknown ID",
                        "-type": id_elem.attrib.get("{urn:com.workday/bsvc}type", "Unknown Type")
                    }
                    for id_elem in location_data_elem.find("{urn:com.workday/bsvc}Location_Hierarchy_Reference", namespaces).findall("{urn:com.workday/bsvc}ID", namespaces)
                ] if location_data_elem.find("{urn:com.workday/bsvc}Location_Hierarchy_Reference", namespaces) is not None else []
            }

            time_profile_reference = {
                "ID": [
                    {
                        "#content": id_elem.text if id_elem is not None else "Unknown ID",
                        "-type": id_elem.attrib.get("{urn:com.workday/bsvc}type", "Unknown Type")
                    }
                    for id_elem in location_data_elem.find("{urn:com.workday/bsvc}Time_Profile_Reference", namespaces).findall("{urn:com.workday/bsvc}ID", namespaces)
                ] if location_data_elem.find("{urn:com.workday/bsvc}Time_Profile_Reference", namespaces) is not None else []
            }

            integration_id_data = {
                "ID": [
                    {
                        "#content": id_elem.text if id_elem is not None else "Unknown ID",
                        "-System_ID": id_elem.attrib.get("{urn:com.workday/bsvc}System_ID", "Unknown Type")
                    }
                    for id_elem in location_data_elem.find("{urn:com.workday/bsvc}Integration_ID_Data", namespaces).findall("{urn:com.workday/bsvc}ID", namespaces)
                ] if location_data_elem.find("{urn:com.workday/bsvc}Integration_ID_Data", namespaces) is not None else []
            }

            locale_reference = {
                "ID": [
                    {
                        "#content": id_elem.text if id_elem is not None else "Unknown ID",
                        "-type": id_elem.attrib.get("{urn:com.workday/bsvc}type", "Unknown Type")
                    }
                    for id_elem in location_data_elem.find("{urn:com.workday/bsvc}Locale_Reference", namespaces).findall("{urn:com.workday/bsvc}ID", namespaces)
                ] if location_data_elem.find("{urn:com.workday/bsvc}Locale_Reference", namespaces) is not None else []
            }

            time_zone_reference = {
                "ID": [
                    {
                        "#content": id_elem.text if id_elem is not None else "Unknown ID",
                        "-type": id_elem.attrib.get("{urn:com.workday/bsvc}type", "Unknown Type")
                    }
                    for id_elem in location_data_elem.find("{urn:com.workday/bsvc}Time_Zone_Reference", namespaces).findall("{urn:com.workday/bsvc}ID", namespaces)
                ] if location_data_elem.find("{urn:com.workday/bsvc}Time_Zone_Reference", namespaces) is not None else []
            }

            default_currency_reference = {
                "ID": [
                    {
                        "#content": id_elem.text if id_elem is not None else "Unknown ID",
                        "-type": id_elem.attrib.get("{urn:com.workday/bsvc}type", "Unknown Type")
                    }
                    for id_elem in location_data_elem.find("{urn:com.workday/bsvc}Default_Currency_Reference", namespaces).findall("{urn:com.workday/bsvc}ID", namespaces)
                ] if location_data_elem.find("{urn:com.workday/bsvc}Default_Currency_Reference", namespaces) is not None else []
            }

            contact_data_elem = location_data_elem.find("{urn:com.workday/bsvc}Contact_Data", namespaces)
            address_data_elem = contact_data_elem.find("{urn:com.workday/bsvc}Address_Data", namespaces) if contact_data_elem is not None else None
            address_data = {
                "-Address_Format_Type": address_data_elem.attrib.get("{urn:com.workday/bsvc}Address_Format_Type"),
                "-Defaulted_Business_Site_Address": address_data_elem.attrib.get("{urn:com.workday/bsvc}Defaulted_Business_Site_Address"),
                "-Effective_Date": address_data_elem.attrib.get("{urn:com.workday/bsvc}Effective_Date"),
                "-Formatted_Address": address_data_elem.attrib.get("{urn:com.workday/bsvc}Formatted_Address"),
                "Address_ID": address_data_elem.find("{urn:com.workday/bsvc}Address_ID", namespaces).text if address_data_elem.find("{urn:com.workday/bsvc}Address_ID", namespaces) is not None else None,
                "Address_Line_Data": {
                    "#content": address_data_elem.find("{urn:com.workday/bsvc}Address_Line_Data", namespaces).text if address_data_elem.find("{urn:com.workday/bsvc}Address_Line_Data", namespaces) is not None else None,
                    "-Descriptor": address_data_elem.find("{urn:com.workday/bsvc}Address_Line_Data", namespaces).attrib.get("{urn:com.workday/bsvc}Descriptor"),
                    "-Type": address_data_elem.find("{urn:com.workday/bsvc}Address_Line_Data", namespaces).attrib.get("{urn:com.workday/bsvc}Type")
                },
                "Address_Reference": {
                    "ID": [
                        {
                            "#content": id_elem.text if id_elem is not None else "Unknown ID",
                            "-type": id_elem.attrib.get("{urn:com.workday/bsvc}type", "Unknown Type")
                        }
                        for id_elem in address_data_elem.find("{urn:com.workday/bsvc}Address_Reference", namespaces).findall("{urn:com.workday/bsvc}ID", namespaces)
                    ] if address_data_elem.find("{urn:com.workday/bsvc}Address_Reference", namespaces) is not None else []
                },
                "Country_Reference": {
                    "ID": [
                        {
                            "#content": id_elem.text if id_elem is not None else "Unknown ID",
                            "-type": id_elem.attrib.get("{urn:com.workday/bsvc}type", "Unknown Type")
                        }
                        for id_elem in address_data_elem.find("{urn:com.workday/bsvc}Country_Reference", namespaces).findall("{urn:com.workday/bsvc}ID", namespaces)
                    ] if address_data_elem.find("{urn:com.workday/bsvc}Country_Reference", namespaces) is not None else []
                },
                "Country_Region_Reference": {
                    "ID": [
                        {
                            "#content": id_elem.text if id_elem is not None else "Unknown ID",
                            "-type": id_elem.attrib.get("{urn:com.workday/bsvc}type", "Unknown Type")
                        }
                        for id_elem in address_data_elem.find("{urn:com.workday/bsvc}Country_Region_Reference", namespaces).findall("{urn:com.workday/bsvc}ID", namespaces)
                    ] if address_data_elem.find("{urn:com.workday/bsvc}Country_Region_Reference", namespaces) is not None else []
                },
                "Country_Region_Descriptor": address_data_elem.find("{urn:com.workday/bsvc}Country_Region_Descriptor", namespaces).text if address_data_elem.find("{urn:com.workday/bsvc}Country_Region_Descriptor", namespaces) is not None else None,
                "Last_Modified": address_data_elem.find("{urn:com.workday/bsvc}Last_Modified", namespaces).text if address_data_elem.find("{urn:com.workday/bsvc}Last_Modified", namespaces) is not None else None,
                "Municipality": address_data_elem.find("{urn:com.workday/bsvc}Municipality", namespaces).text if address_data_elem.find("{urn:com.workday/bsvc}Municipality", namespaces) is not None else None,
                "Number_of_Days": address_data_elem.find("{urn:com.workday/bsvc}Number_of_Days", namespaces).text if address_data_elem.find("{urn:com.workday/bsvc}Number_of_Days", namespaces) is not None else None,
                "Postal_Code": address_data_elem.find("{urn:com.workday/bsvc}Postal_Code", namespaces).text if address_data_elem.find("{urn:com.workday/bsvc}Postal_Code", namespaces) is not None else None,
                "Usage_Data": {
                    "-Public": address_data_elem.find("{urn:com.workday/bsvc}Usage_Data", namespaces).attrib.get("{urn:com.workday/bsvc}Public"),
                    "Type_Data": {
                        "-Primary": address_data_elem.find("{urn:com.workday/bsvc}Usage_Data/{urn:com.workday/bsvc}Type_Data", namespaces).attrib.get("{urn:com.workday/bsvc}Primary"),
                        "Type_Reference": {
                            "ID": [
                                {
                                    "#content": id_elem.text if id_elem is not None else "Unknown ID",
                                    "-type": id_elem.attrib.get("{urn:com.workday/bsvc}type", "Unknown Type")
                                }
                                for id_elem in address_data_elem.find("{urn:com.workday/bsvc}Usage_Data/{urn:com.workday/bsvc}Type_Data/{urn:com.workday/bsvc}Type_Reference", namespaces).findall("{urn:com.workday/bsvc}ID", namespaces)
                            ] if address_data_elem.find("{urn:com.workday/bsvc}Usage_Data/{urn:com.workday/bsvc}Type_Data/{urn:com.workday/bsvc}Type_Reference", namespaces) is not None else []
                        }
                    }
                }
            } if address_data_elem is not None else None

            contact_data = {
                "Address_Data": address_data
            }

            location_data = {
                "Location_ID": location_data_elem.find("{urn:com.workday/bsvc}Location_ID", namespaces).text if location_data_elem.find("{urn:com.workday/bsvc}Location_ID", namespaces) is not None else None,
                "Location_Name": location_data_elem.find("{urn:com.workday/bsvc}Location_Name", namespaces).text if location_data_elem.find("{urn:com.workday/bsvc}Location_Name", namespaces) is not None else None,
                "Location_Usage_Reference": location_usage_reference,
                "Location_Type_Reference": location_type_reference,
                "Location_Hierarchy_Reference": location_hierarchy_reference,
                "Integration_ID_Data": integration_id_data,
                "Inactive": location_data_elem.find("{urn:com.workday/bsvc}Inactive", namespaces).text if location_data_elem.find("{urn:com.workday/bsvc}Inactive", namespaces) is not None else None,
                "Latitude": location_data_elem.find("{urn:com.workday/bsvc}Latitude", namespaces).text if location_data_elem.find("{urn:com.workday/bsvc}Latitude", namespaces) is not None else None,
                "Longitude": location_data_elem.find("{urn:com.workday/bsvc}Longitude", namespaces).text if location_data_elem.find("{urn:com.workday/bsvc}Longitude", namespaces) is not None else None,
                "Altitude": location_data_elem.find("{urn:com.workday/bsvc}Altitude", namespaces).text if location_data_elem.find("{urn:com.workday/bsvc}Altitude", namespaces) is not None else None,
                "Time_Profile_Reference": time_profile_reference,
                "Locale_Reference": locale_reference,
                "Time_Zone_Reference": time_zone_reference,
                "Default_Currency_Reference": default_currency_reference,
                "Contact_Data": contact_data,
            }

            locations.append({
                "Location_Reference": location_reference,
                "Location_Data": location_data
            })

        return locations


    def parse_job_profiles_response(
        self,
        response_data: ET.Element,
        namespaces: Dict[str, str]
    ) -> List[Dict[str, Optional[Union[str | None, List[Dict[str, str]]]]]]:

        job_profiles: List[Dict[str, Optional[Union[str | None, List[Dict[str, str]]]]]] = []

        if response_data is None:
            return job_profiles

        for job_profile in response_data.findall("{urn:com.workday/bsvc}Job_Profile", namespaces):
            job_profile_reference_elem = job_profile.find("{urn:com.workday/bsvc}Job_Profile_Reference", namespaces)
            job_profile_data_elem = job_profile.find("{urn:com.workday/bsvc}Job_Profile_Data", namespaces)

            job_profile_reference = {
                "ID": [
                    {
                        "#content": id_elem.text if id_elem is not None else "Unknown ID",
                        "-type": id_elem.attrib.get("{urn:com.workday/bsvc}type", "Unknown Type")
                    }
                    for id_elem in job_profile_reference_elem.findall("{urn:com.workday/bsvc}ID", namespaces)
                ] if job_profile_reference_elem is not None else []
            }

            job_profile_basic_data_elem = job_profile_data_elem.find("{urn:com.workday/bsvc}Job_Profile_Basic_Data", namespaces) if job_profile_data_elem is not None else None
            job_profile_pay_rate_data_elem = job_profile_data_elem.find("{urn:com.workday/bsvc}Job_Profile_Pay_Rate_Data", namespaces) if job_profile_data_elem is not None else None
            job_profile_exempt_data_elem = job_profile_data_elem.find("{urn:com.workday/bsvc}Job_Profile_Exempt_Data", namespaces) if job_profile_data_elem is not None else None
            job_profile_compensation_data_elem = job_profile_data_elem.find("{urn:com.workday/bsvc}Job_Profile_Compensation_Data", namespaces) if job_profile_data_elem is not None else None
            job_classification_data_elems = job_profile_data_elem.findall("{urn:com.workday/bsvc}Job_Classification_Data", namespaces) if job_profile_data_elem is not None else []
            workers_compensation_code_replacement_data_elem = job_profile_data_elem.find("{urn:com.workday/bsvc}Workers_Compensation_Code_Replacement_Data", namespaces) if job_profile_data_elem is not None else None
            
            job_profile_basic_data = {}

            if job_profile_basic_data_elem is not None:
                job_profile_basic_data["Job_Title"] = job_profile_basic_data_elem.find("{urn:com.workday/bsvc}Job_Title", namespaces).text
                job_profile_basic_data["Inactive"] = job_profile_basic_data_elem.find("{urn:com.workday/bsvc}Inactive", namespaces).text
                job_profile_basic_data["Include_Job_Code_in_Name"] = job_profile_basic_data_elem.find("{urn:com.workday/bsvc}Include_Job_Code_in_Name", namespaces).text
                job_profile_basic_data["Work_Shift_Required"] = job_profile_basic_data_elem.find("{urn:com.workday/bsvc}Work_Shift_Required", namespaces).text
                job_profile_basic_data["Public_Job"] = job_profile_basic_data_elem.find("{urn:com.workday/bsvc}Public_Job", namespaces).text
                job_profile_basic_data["Critical_Job"] = job_profile_basic_data_elem.find("{urn:com.workday/bsvc}Critical_Job", namespaces).text

                job_family_data_elem = job_profile_basic_data_elem.find("{urn:com.workday/bsvc}Job_Family_Data", namespaces)
                job_family_data = {
                    "Job_Family_Reference": {
                        "ID": [
                            {
                                "#content": id_elem.text if id_elem is not None else "Unknown ID",
                                "-type": id_elem.attrib.get("{urn:com.workday/bsvc}type", "Unknown Type")
                            }
                            for id_elem in job_family_data_elem.find("{urn:com.workday/bsvc}Job_Family_Reference", namespaces).findall("{urn:com.workday/bsvc}ID", namespaces)
                        ] if job_family_data_elem.find("{urn:com.workday/bsvc}Job_Family_Reference", namespaces) is not None else []
                    }
                } if job_family_data_elem is not None else None

                job_level_reference = {
                    "ID": [
                        {
                            "#content": id_elem.text if id_elem is not None else "Unknown ID",
                            "-type": id_elem.attrib.get("{urn:com.workday/bsvc}type", "Unknown Type")
                        }
                        for id_elem in job_profile_basic_data_elem.find("{urn:com.workday/bsvc}Job_Level_Reference", namespaces).findall("{urn:com.workday/bsvc}ID", namespaces)
                    ] if job_profile_basic_data_elem.find("{urn:com.workday/bsvc}Job_Level_Reference", namespaces) is not None else []
                }

                management_level_reference = {
                    "ID": [
                        {
                            "#content": id_elem.text if id_elem is not None else "Unknown ID",
                            "-type": id_elem.attrib.get("{urn:com.workday/bsvc}type", "Unknown Type")
                        }
                        for id_elem in job_profile_basic_data_elem.find("{urn:com.workday/bsvc}Management_Level_Reference", namespaces).findall("{urn:com.workday/bsvc}ID", namespaces)
                    ] if job_profile_basic_data_elem.find("{urn:com.workday/bsvc}Management_Level_Reference", namespaces) is not None else []
                }

                referral_payment_plan_reference = {
                    "ID": [
                        {
                            "#content": id_elem.text if id_elem is not None else "Unknown ID",
                            "-type": id_elem.attrib.get("{urn:com.workday/bsvc}type", "Unknown Type")
                        }
                        for id_elem in job_profile_basic_data_elem.find("{urn:com.workday/bsvc}Referral_Payment_Plan_Reference", namespaces).findall("{urn:com.workday/bsvc}ID", namespaces)
                    ] if job_profile_basic_data_elem.find("{urn:com.workday/bsvc}Referral_Payment_Plan_Reference", namespaces) is not None else []
                }

                job_profile_basic_data["Job_Family_Data"] = job_family_data
                job_profile_basic_data["Job_Level_Reference"] = job_level_reference
                job_profile_basic_data["Management_Level_Reference"] = management_level_reference
                job_profile_basic_data["Referral_Payment_Plan_Reference"] = referral_payment_plan_reference

                job_description = job_profile_basic_data_elem.find("{urn:com.workday/bsvc}Job_Description", namespaces) 
                if job_description is not None:
                    job_profile_basic_data["Job_Description"] = job_description.text

            job_profile_pay_rate_data = {
                "Country_Reference": {
                    "ID": [
                        {
                            "#content": id_elem.text if id_elem is not None else "Unknown ID",
                            "-type": id_elem.attrib.get("{urn:com.workday/bsvc}type", "Unknown Type")
                        }
                        for id_elem in job_profile_pay_rate_data_elem.find("{urn:com.workday/bsvc}Country_Reference", namespaces).findall("{urn:com.workday/bsvc}ID", namespaces)
                    ] if job_profile_pay_rate_data_elem is not None and job_profile_pay_rate_data_elem.find("{urn:com.workday/bsvc}Country_Reference", namespaces) is not None else []
                },
                "Pay_Rate_Type_Reference": {
                    "ID": [
                        {
                            "#content": id_elem.text if id_elem is not None else "Unknown ID",
                            "-type": id_elem.attrib.get("{urn:com.workday/bsvc}type", "Unknown Type")
                        }
                        for id_elem in job_profile_pay_rate_data_elem.find("{urn:com.workday/bsvc}Pay_Rate_Type_Reference", namespaces).findall("{urn:com.workday/bsvc}ID", namespaces)
                    ] if job_profile_pay_rate_data_elem is not None and job_profile_pay_rate_data_elem.find("{urn:com.workday/bsvc}Pay_Rate_Type_Reference", namespaces) is not None else []
                }
            } if job_profile_pay_rate_data_elem is not None else None
            
            workers_compensation_code_replacement_data = {
                "Workers_Compensation_Code_Reference": {
                    "ID": [
                        {
                            "#content": id_elem.text if id_elem is not None else "Unknown ID",
                            "-type": id_elem.attrib.get("{urn:com.workday/bsvc}type", "Unknown Type")
                        }
                        for id_elem in workers_compensation_code_replacement_data_elem.find("{urn:com.workday/bsvc}Workers_Compensation_Code_Reference", namespaces).findall("{urn:com.workday/bsvc}ID", namespaces)
                    ] if workers_compensation_code_replacement_data_elem.find("{urn:com.workday/bsvc}Workers_Compensation_Code_Reference", namespaces) is not None else []
                }
            } if workers_compensation_code_replacement_data_elem is not None else None

            job_profile_exempt_data = {
                "Location_Context_Reference": {
                    "ID": [
                        {
                            "#content": id_elem.text if id_elem is not None else "Unknown ID",
                            "-type": id_elem.attrib.get("{urn:com.workday/bsvc}type", "Unknown Type")
                        }
                        for id_elem in job_profile_exempt_data_elem.find("{urn:com.workday/bsvc}Location_Context_Reference", namespaces).findall("{urn:com.workday/bsvc}ID", namespaces)
                    ] if job_profile_exempt_data_elem is not None and job_profile_exempt_data_elem.find("{urn:com.workday/bsvc}Location_Context_Reference", namespaces) is not None else []
                },
                "Job_Exempt": job_profile_exempt_data_elem.find("{urn:com.workday/bsvc}Job_Exempt", namespaces).text if job_profile_exempt_data_elem is not None else None
            } if job_profile_exempt_data_elem is not None else None

            job_profile_compensation_data = {
                "Compensation_Grade_Reference": {
                    "ID": [
                        {
                            "#content": id_elem.text if id_elem is not None else "Unknown ID",
                            "-type": id_elem.attrib.get("{urn:com.workday/bsvc}type", "Unknown Type")
                        }
                        for id_elem in job_profile_compensation_data_elem.find("{urn:com.workday/bsvc}Compensation_Grade_Reference", namespaces).findall("{urn:com.workday/bsvc}ID", namespaces)
                    ] if job_profile_compensation_data_elem is not None and job_profile_compensation_data_elem.find("{urn:com.workday/bsvc}Compensation_Grade_Reference", namespaces) is not None else []
                }
            } if job_profile_compensation_data_elem is not None else None

            job_classifications_data = [
                {
                    "Job_Classifications_Reference": {
                        "ID": [
                            {
                                "#content": id_elem.text if id_elem is not None else "Unknown ID",
                                "-type": id_elem.attrib.get("{urn:com.workday/bsvc}type", "Unknown Type")
                            }
                            for id_elem in job_classification_data_elem.find("{urn:com.workday/bsvc}Job_Classifications_Reference", namespaces).findall("{urn:com.workday/bsvc}ID", namespaces)
                        ] if job_classification_data_elem.find("{urn:com.workday/bsvc}Job_Classifications_Reference", namespaces) is not None else []
                    }
                } for job_classification_data_elem in job_classification_data_elems
            ]

            job_profile_data = {
                "Job_Code": job_profile_data_elem.find("{urn:com.workday/bsvc}Job_Code", namespaces).text if job_profile_data_elem is not None else None,
                "Effective_Date": job_profile_data_elem.find("{urn:com.workday/bsvc}Effective_Date", namespaces).text if job_profile_data_elem is not None else None,
                "Job_Profile_Basic_Data": job_profile_basic_data,
                "Job_Profile_Pay_Rate_Data": job_profile_pay_rate_data,
                "Workers_Compensation_Code_Replacement_Data": workers_compensation_code_replacement_data,
                "Job_Profile_Exempt_Data": job_profile_exempt_data,
                "Job_Profile_Compensation_Data": job_profile_compensation_data,
                "Job_Classification_Data": job_classifications_data,
            }

            job_profiles.append({
                "Job_Profile_Reference": job_profile_reference,
                "Job_Profile_Data": job_profile_data
            })

        return job_profiles
