"""
DynamoDB adapter for LoopForge.

Requires the `dynamodb` extra: pip install loopforge[dynamodb]

Usage:
    from loopforge.adapters.dynamodb import DynamoDBRepository
    from loopforge import LoopService

    repo = DynamoDBRepository(table_name="my-loops")
    service = LoopService(repository=repo)
"""

import logging
import os
from typing import Any, Optional

from loopforge.states import LoopRecord

logger = logging.getLogger(__name__)

try:
    import boto3
    from botocore.exceptions import ClientError
except ImportError:
    raise ImportError("boto3 is required for the DynamoDB adapter. Install it with: pip install loopforge[dynamodb]")


class DynamoDBRepository:
    """
    DynamoDB-backed repository for LoopRecords.

    Table schema:
        Partition key: record_id (S)

    Optional GSI for state queries:
        GSI name: state-index
        Partition key: state (S)
        Sort key: updated_at (S)
    """

    STATE_INDEX = "state-index"

    def __init__(
        self,
        table_name: Optional[str] = None,
        region_name: Optional[str] = None,
        client: Optional[Any] = None,
    ) -> None:
        self._table_name = table_name or os.environ.get("LOOPFORGE_TABLE", "loopforge")
        self._region_name = region_name
        self._client = client
        self._table = None

    @property
    def table(self) -> Any:
        if self._table is None:
            if self._client is None:
                kwargs = {}
                if self._region_name:
                    kwargs["region_name"] = self._region_name
                self._client = boto3.resource("dynamodb", **kwargs)
            self._table = self._client.Table(self._table_name)
        return self._table

    def save(self, record: LoopRecord) -> LoopRecord:
        try:
            self.table.put_item(Item=record.to_dict())
            return record
        except ClientError as e:
            logger.error(f"[loopforge] DynamoDB save failed for {record.record_id}: {e}")
            raise

    def get(self, record_id: str) -> Optional[LoopRecord]:
        try:
            response = self.table.get_item(Key={"record_id": record_id})
            item = response.get("Item")
            if item is None:
                return None
            return LoopRecord.from_dict(item)
        except ClientError as e:
            logger.error(f"[loopforge] DynamoDB get failed for {record_id}: {e}")
            raise

    def delete(self, record_id: str) -> bool:
        try:
            self.table.delete_item(Key={"record_id": record_id})
            return True
        except ClientError as e:
            logger.error(f"[loopforge] DynamoDB delete failed for {record_id}: {e}")
            raise

    def list_by_state(self, state: str, limit: int = 100) -> list[LoopRecord]:
        try:
            response = self.table.query(
                IndexName=self.STATE_INDEX,
                KeyConditionExpression="#s = :state",
                ExpressionAttributeNames={"#s": "state"},
                ExpressionAttributeValues={":state": state},
                Limit=limit,
                ScanIndexForward=False,
            )
            return [LoopRecord.from_dict(item) for item in response.get("Items", [])]
        except ClientError as e:
            logger.error(f"[loopforge] DynamoDB list_by_state failed: {e}")
            raise
