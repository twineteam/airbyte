import os

CURRENT_DIR: str = os.path.dirname(os.path.realpath(__file__))
XML_DIR: str = CURRENT_DIR.replace("utils", "xml")


class RequestConstructor:
    def __init__(self, base_path: str = XML_DIR) -> None:
        self.base_path: str = base_path
        self.base_template: str = self.read_xml_file("base.xml")
        self.header_template: str = self.read_xml_file("header.xml")

    def read_xml_file(self, filename: str) -> str:
        with open(os.path.join(self.base_path, filename), "r") as file:
            return file.read()

    def construct_body(
        self,
        file_name: str,
        tenant: str,
        username: str,
        password: str,
        page: int,
        per_page: int = 200,
    ) -> str:
        specific_xml_content: str = self.read_xml_file(file_name)
        if "PAGE" in specific_xml_content:
            specific_xml_content = specific_xml_content.replace("PAGE", str(page))
        if "PER_PAGE" in specific_xml_content:
            specific_xml_content = specific_xml_content.replace("PER_PAGE", str(per_page))

        header_content: str = self.header_template % (f"{username}@{tenant}", password)
        full_xml: str = self.base_template % (header_content, specific_xml_content)

        return full_xml
