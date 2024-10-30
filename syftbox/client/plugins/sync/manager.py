import time
from threading import Thread

from loguru import logger

from syftbox.client.plugins.sync.consumer import SyncConsumer
from syftbox.client.plugins.sync.endpoints import get_datasite_states
from syftbox.client.plugins.sync.queue import SyncQueue, SyncQueueItem
from syftbox.client.plugins.sync.sync import DatasiteState, FileChangeInfo
from syftbox.lib import Client


class SyncManager:
    def __init__(self, client: Client):
        self.client = client
        self.queue = SyncQueue()
        self.consumer = SyncConsumer(client=self.client, queue=self.queue)

    def start(self):
        def _start(manager: SyncManager):
            while True:
                manager.run_single_thread()
                time.sleep(1)

        t = Thread(target=_start, args=[self])
        t.start()

    def setup(self):
        self.change_log_folder.mkdir(exist_ok=True)

    def enqueue(self, change: FileChangeInfo) -> None:
        self.queue.put(SyncQueueItem(priority=change.get_priority(), data=change))

    def get_datasite_states(self) -> list[DatasiteState]:
        try:
            remote_datasite_states = get_datasite_states(self.client.server_client, email=self.client.email)
        except Exception as e:
            logger.error(f"Failed to retrieve datasites from server, only syncing own datasite. Reason: {e}")
            remote_datasite_states = {}

        # Ensure we are always syncing own datasite
        if self.client.email not in remote_datasite_states:
            remote_datasite_states[self.client.email] = []

        datasite_states = [
            DatasiteState(self.client, email, remote_state=remote_state)
            for email, remote_state in remote_datasite_states.items()
        ]
        return datasite_states

    def enqueue_datasite_changes(self, datasite: DatasiteState):
        try:
            permission_changes, file_changes = datasite.get_out_of_sync_files()
            total = len(permission_changes) + len(file_changes)
            if total != 0:
                logger.debug(
                    f"Enqueuing {len(permission_changes)} permissions and {len(file_changes)} files for {datasite.email}"
                )
        except Exception as e:
            logger.error(f"Failed to get out of sync files for {datasite.email}. Reason: {e}")
            permission_changes, file_changes = [], []

        for change in permission_changes + file_changes:
            self.enqueue(change)

    def run_single_thread(self):
        # NOTE first implementation will be unthreaded and just loop through all datasites

        datasite_states = self.get_datasite_states()
        logger.info(f"Syncing {len(datasite_states)} datasites")
        logger.debug(f"Datasites: {', '.join([datasite.email for datasite in datasite_states])}")

        for datasite_state in datasite_states:
            self.enqueue_datasite_changes(datasite_state)

        self.consumer.consume_all()
