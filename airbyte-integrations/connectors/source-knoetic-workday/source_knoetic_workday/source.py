import base64
import logging
import time
from abc import ABC
from datetime import datetime
from typing import Any, Iterable, List, Mapping, MutableMapping, Optional, Tuple

import requests
from airbyte_cdk.sources import AbstractSource
from airbyte_cdk.sources.streams import Stream
from airbyte_cdk.sources.streams.call_rate import APIBudget
from airbyte_cdk.sources.streams.http import HttpStream

from .utils.requests import WorkdayRequest

logger = logging.getLogger(__name__)


_INCOMING_DATETIME_FORMAT = "%Y-%m-%dT%H:%M:%S"


class KnoeticWorkdayStream(HttpStream, ABC):
    """
    Each stream should extend this class (or another abstract subclass of it) to specify behavior unique to that stream.

    Typically for REST APIs each stream corresponds to a resource in the API. For example:

    if the API contains the endpoints
        - POST Human_Resources/37.2

    then you should have these classes:
    - `class KnoeticWorkdayStream(HttpStream, ABC)` which is the current class
    - `class Workers(KnoeticWorkdayStream)` contains behavior to pull data for workers using `Human_Resources/37.2`
    - `class OrganizationHierarchies(KnoeticWorkdayStream)` contains behavior to pull data for organization hierarchies using `Human_Resources/37.2`
    - `class Ethnicities(KnoeticWorkdayStream)` contains behavior to pull data for ethnicities using `Human_Resources/37.2`
    - `class GenderIdentities(KnoeticWorkdayStream)` contains behavior to pull data for gender identities using `Human_Resources/37.2`
    - `class Locations(KnoeticWorkdayStream)` contains behavior to pull data for locations using `Human_Resources/37.2`
    - `class JobProfiles(KnoeticWorkdayStream)` contains behavior to pull data for job profiles using `Human_Resources/37.2`
    - `class SexualOrientations(KnoeticWorkdayStream)` contains behavior to pull data for sexual orientations using `Human_Resources/37.2`

    if the API contains the endpoints
        - POST Staffing/37.2

    then you should have these classes:
    - `class Positions(KnoeticWorkdayStream)` contains behavior to pull data for positions using `Staffing/37.2`

    if the API contains the endpoints
        - POST Integrations/37.2

    then you should have these classes:
    - `class References(KnoeticWorkdayStream)` contains behavior to pull data for reference types using `Integrations/37.2`

    if the API contains the endpoints
        - GET customreport2

    then you should have these classes:
    - `class BaseCustomReport(KnoeticWorkdayStream)` contains behavior to pull data for:
        - a base snapshot report using `customreport2`
        - a base historical report for compensation using `customreport2`
        - a base historical report for job using `customreport2`

    If some streams implement incremental sync, it is typical to create another class
    `class IncrementalKnoeticWorkdayStream((KnoeticWorkdayStream), ABC)` then have concrete stream
    implementations extend it. An example is provided below.

    See the reference docs for the full list of configurable options.
    """

    def __init__(
        self,
        *,
        tenant: str,
        url: str,
        username: str,
        password: str,
        workday_request: WorkdayRequest,
        page: int = 1,
        per_page: int = 200,
        api_budget: APIBudget | None = None,
        web_service: str = "Human_Resources",
    ):
        super().__init__(api_budget)
        self.api_version = "37.2"
        self.web_service = web_service
        self._cursor_field = "Last_Modified"
        self.tenant = tenant
        self.url = url
        self.username = username
        self.password = password
        self.workday_request = workday_request
        self.page = page
        self.per_page = per_page

    @property
    def http_method(self) -> str:
        """
        :return str: The HTTP method for the request. Default is "GET".
        """
        return "POST"

    @property
    def url_base(self) -> str:
        """
        :return The base URL for the API.
        """

        return f"{self.url}"

    def next_page_token(self, response: requests.Response) -> Optional[Mapping[str, Any]]:
        """
        :param response: the most recent response from the API
        :return If there is another page in the result, a mapping (e.g: dict) containing information
        needed to query the next page in the response. If there are no more pages in the result, return None.
        """

        response_text = response.text

        import xml.etree.ElementTree as ET

        root = ET.fromstring(response_text)
        ns = {"wd": "urn:com.workday/bsvc"}

        # Find the current page and total pages
        current_page_elem = root.find(".//wd:Page", ns)
        total_pages_elem = root.find(".//wd:Total_Pages", ns)

        if (
            current_page_elem is not None
            and current_page_elem.text is not None
            and total_pages_elem is not None
            and total_pages_elem.text is not None
        ):
            current_page = int(current_page_elem.text)
            total_pages = int(total_pages_elem.text)

            # Calculate the next page number if available
            if current_page < total_pages:
                next_page = current_page + 1
                return {"page": next_page}
            else:
                return None
        else:
            raise ValueError("Required XML elements not found")

    def path(
        self,
        *,
        stream_state: Mapping[str, Any] | None = None,
        stream_slice: Mapping[str, Any] | None = None,
        next_page_token: Mapping[str, Any] | None = None,
    ) -> str:
        return f"{self.tenant}/{self.web_service}/{self.api_version}"


class Workers(KnoeticWorkdayStream):
    """
    Represents a stream of `worker` data from the Knoetic Workday source.
    It inherits from the KnoeticWorkdayStream class.
    """

    primary_key = None

    def __init__(
        self,
        tenant: str,
        url: str,
        username: str,
        password: str,
        workday_request: WorkdayRequest,
        page: int = 1,
        per_page: int = 200,
        api_budget: APIBudget | None = None,
    ):
        super().__init__(
            tenant=tenant,
            url=url,
            username=username,
            password=password,
            workday_request=workday_request,
            page=page,
            per_page=per_page,
            api_budget=api_budget,
        )

    def request_body_data(
        self,
        stream_state: Mapping[str, Any] | None,
        stream_slice: Mapping[str, Any] | None = None,
        next_page_token: Mapping[str, Any] | None = None,
    ) -> str:
        """
        Override to define the request body data for the request.
        """

        if next_page_token:
            self.page = next_page_token["page"]

        return self.workday_request.construct_request_body(
            "workers.xml",
            self.tenant,
            self.username,
            self.password,
            self.page,
            self.per_page,
        )

    def parse_response(
        self,
        response: requests.Response,
        *,
        stream_state: Mapping[str, Any],
        stream_slice: Mapping[str, Any] | None = None,
        next_page_token: Mapping[str, Any] | None = None,
    ) -> Iterable[Mapping[str, Any]]:

        response_json = self.workday_request.parse_response(response, stream_name="workers")

        yield from response_json


class OrganizationHierarchies(KnoeticWorkdayStream):
    """
    Represents a collection of streams of `organization hierarchies` data from the Knoetic Workday source.
    It inherits from the KnoeticWorkdayStream class.
    """

    primary_key = None

    def __init__(
        self,
        tenant: str,
        url: str,
        username: str,
        password: str,
        workday_request: WorkdayRequest,
        page: int = 1,
        per_page: int = 200,
        api_budget: APIBudget | None = None,
    ):
        super().__init__(
            tenant=tenant,
            url=url,
            username=username,
            password=password,
            workday_request=workday_request,
            page=page,
            per_page=per_page,
            api_budget=api_budget,
        )

    def request_body_data(
        self,
        stream_state: Mapping[str, Any] | None,
        stream_slice: Mapping[str, Any] | None = None,
        next_page_token: Mapping[str, Any] | None = None,
    ) -> str:
        """
        Override to define the request body data for the request.
        """

        return self.workday_request.construct_request_body(
            "organization_hierarchies.xml",
            self.tenant,
            self.username,
            self.password,
            self.page,
            self.per_page,
        )

    def parse_response(
        self,
        response: requests.Response,
        *,
        stream_state: Mapping[str, Any],
        stream_slice: Mapping[str, Any] | None = None,
        next_page_token: Mapping[str, Any] | None = None,
    ) -> Iterable[Mapping[str, Any]]:
        response_json = self.workday_request.parse_response(response, stream_name="organization_hierarchies")
        return response_json


class Ethnicities(KnoeticWorkdayStream):
    """
    Represents a collection of streams of `ethnicities` data from the Knoetic Workday source.
    It inherits from the KnoeticWorkdayStream class.
    """

    primary_key = None

    def __init__(
        self,
        tenant: str,
        url: str,
        username: str,
        password: str,
        workday_request: WorkdayRequest,
        page: int = 1,
        per_page: int = 200,
        api_budget: APIBudget | None = None,
    ):
        super().__init__(
            tenant=tenant,
            url=url,
            username=username,
            password=password,
            workday_request=workday_request,
            page=page,
            per_page=per_page,
            api_budget=api_budget,
        )

    def request_body_data(
        self,
        stream_state: Mapping[str, Any] | None,
        stream_slice: Mapping[str, Any] | None = None,
        next_page_token: Mapping[str, Any] | None = None,
    ) -> str:
        """
        Override to define the request body data for the request.
        """

        return self.workday_request.construct_request_body(
            "ethnicities.xml",
            self.tenant,
            self.username,
            self.password,
            self.page,
            self.per_page,
        )

    def parse_response(
        self,
        response: requests.Response,
        *,
        stream_state: Mapping[str, Any],
        stream_slice: Mapping[str, Any] | None = None,
        next_page_token: Mapping[str, Any] | None = None,
    ) -> Iterable[Mapping[str, Any]]:
        response_json = self.workday_request.parse_response(response, stream_name="ethnicities")
        return response_json


class GenderIdentities(KnoeticWorkdayStream):
    """
    Represents a collection of streams of `gender_identities` data from the Knoetic Workday source.
    It inherits from the KnoeticWorkdayStream class.
    """

    primary_key = None

    def __init__(
        self,
        tenant: str,
        url: str,
        username: str,
        password: str,
        workday_request: WorkdayRequest,
        page: int = 1,
        per_page: int = 200,
        api_budget: APIBudget | None = None,
    ):
        super().__init__(
            tenant=tenant,
            url=url,
            username=username,
            password=password,
            workday_request=workday_request,
            page=page,
            per_page=per_page,
            api_budget=api_budget,
        )

    def request_body_data(
        self,
        stream_state: Mapping[str, Any] | None,
        stream_slice: Mapping[str, Any] | None = None,
        next_page_token: Mapping[str, Any] | None = None,
    ) -> str:
        """
        Override to define the request body data for the request.
        """

        return self.workday_request.construct_request_body(
            "gender_identities.xml",
            self.tenant,
            self.username,
            self.password,
            self.page,
            self.per_page,
        )

    def parse_response(
        self,
        response: requests.Response,
        *,
        stream_state: Mapping[str, Any],
        stream_slice: Mapping[str, Any] | None = None,
        next_page_token: Mapping[str, Any] | None = None,
    ) -> Iterable[Mapping[str, Any]]:
        response_json = self.workday_request.parse_response(response, stream_name="gender_identities")
        return response_json


class Locations(KnoeticWorkdayStream):
    """
    Represents a collection of streams of `locations` data from the Knoetic Workday source.
    It inherits from the KnoeticWorkdayStream class.
    """

    primary_key = None

    def __init__(
        self,
        tenant: str,
        url: str,
        username: str,
        password: str,
        workday_request: WorkdayRequest,
        page: int = 1,
        per_page: int = 200,
        api_budget: APIBudget | None = None,
    ):
        super().__init__(
            tenant=tenant,
            url=url,
            username=username,
            password=password,
            workday_request=workday_request,
            page=page,
            per_page=per_page,
            api_budget=api_budget,
        )

    def request_body_data(
        self,
        stream_state: Mapping[str, Any] | None,
        stream_slice: Mapping[str, Any] | None = None,
        next_page_token: Mapping[str, Any] | None = None,
    ) -> str:
        """
        Override to define the request body data for the request.
        """

        return self.workday_request.construct_request_body(
            "locations.xml",
            self.tenant,
            self.username,
            self.password,
            self.page,
            self.per_page,
        )

    def parse_response(
        self,
        response: requests.Response,
        *,
        stream_state: Mapping[str, Any],
        stream_slice: Mapping[str, Any] | None = None,
        next_page_token: Mapping[str, Any] | None = None,
    ) -> Iterable[Mapping[str, Any]]:
        response_json = self.workday_request.parse_response(response, stream_name="locations")
        return response_json


class JobProfiles(KnoeticWorkdayStream):
    """
    Represents a collection of streams of `job_profiles` data from the Knoetic Workday source.
    It inherits from the KnoeticWorkdayStream class.
    """

    primary_key = None

    def __init__(
        self,
        tenant: str,
        url: str,
        username: str,
        password: str,
        workday_request: WorkdayRequest,
        page: int = 1,
        per_page: int = 200,
        api_budget: APIBudget | None = None,
    ):
        super().__init__(
            tenant=tenant,
            url=url,
            username=username,
            password=password,
            workday_request=workday_request,
            page=page,
            per_page=per_page,
            api_budget=api_budget,
        )

    def request_body_data(
        self,
        stream_state: Mapping[str, Any] | None,
        stream_slice: Mapping[str, Any] | None = None,
        next_page_token: Mapping[str, Any] | None = None,
    ) -> str:
        """
        Override to define the request body data for the request.
        """

        return self.workday_request.construct_request_body(
            "job_profiles.xml",
            self.tenant,
            self.username,
            self.password,
            self.page,
            self.per_page,
        )

    def parse_response(
        self,
        response: requests.Response,
        *,
        stream_state: Mapping[str, Any],
        stream_slice: Mapping[str, Any] | None = None,
        next_page_token: Mapping[str, Any] | None = None,
    ) -> Iterable[Mapping[str, Any]]:
        response_json = self.workday_request.parse_response(response, stream_name="job_profiles")
        return response_json


class Positions(KnoeticWorkdayStream):
    """
    Represents a collection of streams of `positions` data from the Knoetic Workday source.
    It inherits from the KnoeticWorkdayStream class.
    """

    primary_key = None

    def __init__(
        self,
        tenant: str,
        url: str,
        username: str,
        password: str,
        workday_request: WorkdayRequest,
        page: int = 1,
        per_page: int = 200,
        api_budget: APIBudget | None = None,
    ):
        super().__init__(
            tenant=tenant,
            url=url,
            username=username,
            password=password,
            workday_request=workday_request,
            page=page,
            per_page=per_page,
            api_budget=api_budget,
            web_service="Staffing",
        )

    def request_body_data(
        self,
        stream_state: Mapping[str, Any] | None,
        stream_slice: Mapping[str, Any] | None = None,
        next_page_token: Mapping[str, Any] | None = None,
    ) -> str:
        """
        Override to define the request body data for the request.
        """

        return self.workday_request.construct_request_body(
            "positions.xml",
            self.tenant,
            self.username,
            self.password,
            self.page,
            self.per_page,
        )

    def parse_response(
        self,
        response: requests.Response,
        *,
        stream_state: Mapping[str, Any],
        stream_slice: Mapping[str, Any] | None = None,
        next_page_token: Mapping[str, Any] | None = None,
    ) -> Iterable[Mapping[str, Any]]:
        response_json = self.workday_request.parse_response(response, stream_name="positions")
        return response_json


class SexualOrientations(KnoeticWorkdayStream):
    """
    Represents a collection of streams of `positions` data from the Knoetic Workday source.
    It inherits from the KnoeticWorkdayStream class.
    """

    primary_key = None

    def __init__(
        self,
        tenant: str,
        url: str,
        username: str,
        password: str,
        workday_request: WorkdayRequest,
        page: int = 1,
        per_page: int = 200,
        api_budget: APIBudget | None = None,
    ):
        super().__init__(
            tenant=tenant,
            url=url,
            username=username,
            password=password,
            workday_request=workday_request,
            page=page,
            per_page=per_page,
            api_budget=api_budget,
        )

    def request_body_data(
        self,
        stream_state: Mapping[str, Any] | None,
        stream_slice: Mapping[str, Any] | None = None,
        next_page_token: Mapping[str, Any] | None = None,
    ) -> str:
        """
        Override to define the request body data for the request.
        """

        return self.workday_request.construct_request_body(
            "sexual_orientations.xml",
            self.tenant,
            self.username,
            self.password,
            self.page,
            self.per_page,
        )

    def parse_response(
        self,
        response: requests.Response,
        *,
        stream_state: Mapping[str, Any],
        stream_slice: Mapping[str, Any] | None = None,
        next_page_token: Mapping[str, Any] | None = None,
    ) -> Iterable[Mapping[str, Any]]:
        response_json = self.workday_request.parse_response(response, stream_name="sexual_orientations")
        return response_json


class References(KnoeticWorkdayStream):
    """
    Represents a collection of streams of `references` data from the Knoetic Workday source.
    It inherits from the KnoeticWorkdayStream class.
    """

    primary_key = None

    def __init__(
        self,
        tenant: str,
        url: str,
        username: str,
        password: str,
        workday_request: WorkdayRequest,
        page: int = 1,
        per_page: int = 200,
        api_budget: APIBudget | None = None,
    ):
        super().__init__(
            tenant=tenant,
            url=url,
            username=username,
            password=password,
            workday_request=workday_request,
            page=page,
            per_page=per_page,
            api_budget=api_budget,
            web_service="Integrations",
        )
        self.reference_types = [
            "Contingent_Worker_Type_ID",
            "Employee_Type_ID",
            "Ethnicity_ID",
            "Event_Classification_Subcategory_ID",
            "Gender_Code",
            "Job_Category_ID",
            "Job_Family_ID",
            "Job_Level_ID",
            "Management_Level_ID",
            "Marital_Status_ID",
            "Organization_Subtype_ID",
            "Organization_Type_ID",
        ]
        self.current_reference_type = None

    def request_body_data(
        self,
        stream_state: Mapping[str, Any] | None,
        stream_slice: Mapping[str, Any] | None = None,
        next_page_token: Mapping[str, Any] | None = None,
    ) -> str:
        """
        Override to define the request body data for the request.
        """
        # Stream slice per reference type
        if stream_slice:
            self.current_reference_type = stream_slice["reference_type"]

        return self.workday_request.construct_request_body(
            "references.xml", self.tenant, self.username, self.password, self.page, self.per_page
        ).replace("REFERENCE_SUBCATEGORY_TYPE", self.current_reference_type)

    def stream_slices(self, **kwargs) -> Iterable[Optional[Mapping[str, Any]]]:
        """
        Override to provide slices for each reference type.
        """
        return [{"reference_type": ref_type} for ref_type in self.reference_types]

    def parse_response(
        self,
        response: requests.Response,
        *,
        stream_state: Mapping[str, Any],
        stream_slice: Mapping[str, Any] | None = None,
        next_page_token: Mapping[str, Any] | None = None,
    ) -> Iterable[Mapping[str, Any]]:
        response_json = self.workday_request.parse_response(response, stream_name="references")
        for record in response_json:
            yield record


class BaseCustomReport(KnoeticWorkdayStream):
    primary_key = None

    def __init__(
        self,
        tenant: str,
        url: str,
        username: str,
        password: str,
        base_snapshot_report: str,
        workday_request: WorkdayRequest,
        page: int = 1,
        per_page: int = 200,
        api_budget: APIBudget | None = None,
        base_historical_report_compensation: Optional[str] = None,
        base_historical_report_job: Optional[str] = None,
    ):
        super().__init__(
            tenant=tenant,
            url=url,
            username=username,
            password=password,
            workday_request=workday_request,
            page=page,
            per_page=per_page,
            api_budget=api_budget,
            web_service="customreport2",
        )
        self.base_snapshot_report = base_snapshot_report
        self.base_historical_report_compensation = base_historical_report_compensation
        self.base_historical_report_job = base_historical_report_job

    @property
    def http_method(self) -> str:
        return "GET"

    def path(
        self,
        *,
        stream_state: Mapping[str, Any] | None = None,
        stream_slice: Mapping[str, Any] | None = None,
        next_page_token: Mapping[str, Any] | None = None,
    ) -> str:
        report_name = stream_slice.get("report_name")
        format_type = stream_slice.get("format_type")

        url_query_char = "&" if "?" in report_name else "?"
        return f"customreport2/{self.tenant}/{self.username}/{report_name}{url_query_char}format={format_type}"

    def request_headers(
        self,
        *,
        stream_state: Mapping[str, Any] | None = None,
        stream_slice: Mapping[str, Any] | None = None,
        next_page_token: Mapping[str, Any] | None = None,
    ) -> Mapping[str, Any]:
        format_type = "text/csv"
        if stream_slice:
            format_type = "application/xml" if stream_slice.get("format_type") == "xml" else "text/csv"

        token = base64.b64encode(f"{self.username}:{self.password}".encode("utf-8")).decode("utf-8")
        return {"Content-Type": "application/json", "Accept": format_type, "Authorization": f"Basic {token}"}

    def stream_slices(self, **kwargs) -> Iterable[Optional[Mapping[str, Any]]]:
        slices = []
        if self.base_snapshot_report:
            slices.append({"report_name": self.base_snapshot_report, "format_type": "csv"})
        if self.base_historical_report_compensation:
            slices.append({"report_name": self.base_historical_report_compensation, "format_type": "xml"})
        if self.base_historical_report_job:
            slices.append({"report_name": self.base_historical_report_job, "format_type": "xml"})
        return slices

    def parse_response(
        self,
        response: requests.Response,
        *,
        stream_state: Mapping[str, Any],
        stream_slice: Mapping[str, Any] | None = None,
        next_page_token: Mapping[str, Any] | None = None,
    ) -> Iterable[Mapping[str, Any]]:
        if stream_slice and stream_slice.get("format_type") == "xml":
            if stream_slice.get("report_name") == self.base_historical_report_compensation:
                response_json = self.workday_request.parse_response(
                    response, stream_name="base_historical_report_compensation"
                )
                for record in response_json:
                    yield record

            if stream_slice.get("report_name") == self.base_historical_report_job:
                response_json = self.workday_request.parse_response(response, stream_name="base_historical_report_job")
                for record in response_json:
                    yield record

        else:
            response_json = self.workday_request.parse_response(response, stream_name="base_snapshot_report")
            for record in response_json:
                yield record


# TODO (pebabion): Implement incremental streams
class IncrementalKnoeticWorkdayStream(KnoeticWorkdayStream, ABC):
    """
    TODO: write docs
    """

    # Checkpoint stream reads after N records. This prevents re-reading of data if the stream fails for any reason.
    state_checkpoint_interval = 1000

    @property
    def cursor_field(self) -> str:
        """
        TODO (pebabion 2024-05-14):
        Override to return the cursor field used by this stream e.g: an API entity might always use
        created_at as the cursor field. This is usually id or date based. This field's presence tells
        the framework this in an incremental stream. Required for incremental.

        :return str: The name of the cursor field.
        """
        return "Last_Modified"

    def get_updated_state(
        self,
        current_stream_state: MutableMapping[str, Any],
        latest_record: Mapping[str, Any],
    ) -> Mapping[str, Any]:
        """
        Override to determine the latest state after reading the latest record. This typically compared
        the cursor_field from the latest record and the current state and picks the 'most' recent cursor.
        This is how a stream's state is determined. Required for incremental.
        """
        state_value = max(
            current_stream_state.get(self.cursor_field, 0),
            datetime.strptime(latest_record.get(self._cursor_field, ""), _INCOMING_DATETIME_FORMAT).timestamp(),
        )
        return {self._cursor_field: state_value}


class WorkerDetail(IncrementalKnoeticWorkdayStream):
    """
    TODO: Write docs
    """

    # TODO: Fill in the cursor_field. Required.
    cursor_field = "start_date"

    # TODO: Fill in the primary key. Required. This is usually a unique field in the stream, like an ID or a timestamp.
    primary_key = "employee_id"

    # TODO: implement stream_slices


class SourceKnoeticWorkday(AbstractSource):
    def check_connection(self, logger, config) -> Tuple[bool, any]:
        """
        TODO: Implement a connection check to validate that the user-provided config can be used to
        connect to the underlying API

        See `https://github.com/airbytehq/airbyte/blob/master/airbyte-integrations/
        connectors/source-stripe/source_stripe/source.py#L232` for an example.

        :param config:  the user-input config object conforming to the connector's spec.yaml
        :param logger:  logger object
        :return Tuple[bool, any]: (True, None) if the input config can be used to connect to the API
            successfully, (False, error) otherwise.
        """
        return True, None

    def streams(self, config: Mapping[str, Any]) -> List[Stream]:
        """
        :param config: A Mapping of the user input configuration as defined in the connector spec.
        """

        tenant = config["tenant"]

        # url should end with a trailing slash
        url = config["url"]
        if not url.endswith("/"):
            url = f"{url}/"

        username = config["username"]
        password = config["password"]
        base_snapshot_report = config.get("base_snapshot_report")
        base_historical_report_compensation = config.get("base_historical_report_compensation")
        base_historical_report_job = config.get("base_historical_report_job")
        per_page = config.get("per_page", 200)

        return [
            Workers(
                tenant=tenant,
                url=url,
                username=username,
                password=password,
                per_page=per_page,
                workday_request=WorkdayRequest(),
            ),
            OrganizationHierarchies(
                tenant=tenant,
                url=url,
                username=username,
                password=password,
                per_page=per_page,
                workday_request=WorkdayRequest(),
            ),
            Ethnicities(
                tenant=tenant,
                url=url,
                username=username,
                password=password,
                per_page=per_page,
                workday_request=WorkdayRequest(),
            ),
            GenderIdentities(
                tenant=tenant,
                url=url,
                username=username,
                password=password,
                per_page=per_page,
                workday_request=WorkdayRequest(),
            ),
            Locations(
                tenant=tenant,
                url=url,
                username=username,
                password=password,
                per_page=per_page,
                workday_request=WorkdayRequest(),
            ),
            JobProfiles(
                tenant=tenant,
                url=url,
                username=username,
                password=password,
                per_page=per_page,
                workday_request=WorkdayRequest(),
            ),
            Positions(
                tenant=tenant,
                url=url,
                username=username,
                password=password,
                per_page=per_page,
                workday_request=WorkdayRequest(),
            ),
            SexualOrientations(
                tenant=tenant,
                url=url,
                username=username,
                password=password,
                per_page=per_page,
                workday_request=WorkdayRequest(),
            ),
            References(
                tenant=tenant,
                url=url,
                username=username,
                password=password,
                per_page=per_page,
                workday_request=WorkdayRequest(),
            ),
            BaseCustomReport(
                tenant=tenant,
                url=url,
                username=username,
                password=password,
                base_snapshot_report=base_snapshot_report,
                base_historical_report_compensation=base_historical_report_compensation,
                base_historical_report_job=base_historical_report_job,
                per_page=per_page,
                workday_request=WorkdayRequest(),
            ),
        ]
