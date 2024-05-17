import logging
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

    Typically for REST APIs each stream corresponds to a resource in the API. For example if the API
    contains the endpoints
        - GET Human_Resources/37.2

    then you should have three classes:
    - `class KnoeticWorkdayStream(HttpStream, ABC)` which is the current class
    - `class Workers(KnoeticWorkdayStream)` contains behavior to pull data for workers using `Human_Resources/37.2`
    - `class OrganizationHierarchies(KnoeticWorkdayStream)` contains behavior to pull data for
    organization hierarchies using `Human_Resources/37.2`

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
        stream_name: str,
        base_snapshot_report: str,
        workday_request: WorkdayRequest,
        page: int = 1,
        per_page: int = 200,
        api_budget: APIBudget | None = None,
    ):
        super().__init__(api_budget)
        self.api_version = "37.2"
        self._cursor_field = "Last_Modified"
        self.tenant = tenant
        self.url = url
        self.username = username
        self.password = password
        self.base_snapshot_report = base_snapshot_report
        self.workday_request = workday_request
        self.page = page
        self.per_page = per_page
        self.stream_name = stream_name

    def next_page_token(self, response: requests.Response) -> Optional[Mapping[str, Any]]:
        """
        This method should return a Mapping (e.g: dict) containing whatever information required to
        make paginated requests. This dict is passed to most other methods in this class to help you
        form headers, request bodies, query params, etc..

        For example, if the API accepts a 'page' parameter to determine which page of the result to
        return, and a response from the API contains a 'page' number, then this method should probably
        return a dict {'page': response.json()['page'] + 1} to increment the page count by 1.
        The request_params method should then read the input next_page_token and set the
        'page' param to next_page_token['page'].

        :param response: the most recent response from the API
        :return If there is another page in the result, a mapping (e.g: dict) containing information
        needed to query the next page in the response. If there are no more pages in the result, return None.
        """
        return None

    @property
    def url_base(self) -> str:
        """
        :return The base URL for the API.
        """

        return f"{self.url}"

    def path(
        self,
        *,
        stream_state: Mapping[str, Any] | None = None,
        stream_slice: Mapping[str, Any] | None = None,
        next_page_token: Mapping[str, Any] | None = None,
    ) -> str:
        return f"{self.tenant}/Human_Resources/{self.api_version}"


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
        base_snapshot_report: str,
        workday_request: WorkdayRequest,
        page: int = 1,
        per_page: int = 200,
        api_budget: APIBudget | None = None,
    ):
        super().__init__(
            tenant=tenant,
            stream_name="workers",
            url=url,
            username=username,
            password=password,
            base_snapshot_report=base_snapshot_report,
            workday_request=workday_request,
            page=page,
            per_page=per_page,
            api_budget=api_budget,
        )

    @property
    def http_method(self) -> str:
        """
        :return str: The HTTP method for the request. Default is "GET".
        """
        return "POST"

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
            "workers.xml",
            self.tenant,
            self.username,
            self.password,
            self.page,
            self.per_page,
            self.stream_name,
        )

    def parse_response(
        self,
        response: requests.Response,
        *,
        stream_state: Mapping[str, Any],
        stream_slice: Mapping[str, Any] | None = None,
        next_page_token: Mapping[str, Any] | None = None,
    ) -> Iterable[Mapping[str, Any]]:

        response_json = self.workday_request.parse_workers_response(response)

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
        base_snapshot_report: str,
        workday_request: WorkdayRequest,
        page: int = 1,
        per_page: int = 200,
        api_budget: APIBudget | None = None,
    ):
        super().__init__(
            tenant,
            url,
            username,
            password,
            base_snapshot_report,
            workday_request,
            page,
            per_page,
            api_budget,
            stream_name="organization_hierarchies",
        )

    @property
    def url_base(self) -> str:
        """
        :return The base URL for the API.
        """

        return self.endpoint

    @property
    def http_method(self) -> str:
        """
        :return str: The HTTP method for the request. Default is "GET".
        """
        return "POST"

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
            self.stream_name,
        )


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
        TODO: Replace the streams below with your own streams.

        :param config: A Mapping of the user input configuration as defined in the connector spec.
        """

        tenant = config["tenant"]
        url = config["url"]
        username = config["username"]
        password = config["password"]
        base_snapshot_report = config["base_snapshot_report"]
        per_page = config.get("per_page", 200)

        return [
            Workers(
                tenant=tenant,
                url=url,
                username=username,
                password=password,
                base_snapshot_report=base_snapshot_report,
                per_page=per_page,
                workday_request=WorkdayRequest(),
            ),
            OrganizationHierarchies(
                tenant=tenant,
                url=url,
                username=username,
                password=password,
                base_snapshot_report=base_snapshot_report,
                per_page=per_page,
                workday_request=WorkdayRequest(),
            ),
        ]
