import asyncio
import datetime
import os
from typing import Union, List
import re

from rich.text import Text
from rich.prompt import Prompt
from rich.console import Console
from rich.table import Table

from icloud import HideMyEmail


MAX_CONCURRENT_TASKS = 5
SLEEP_INTERVAL = 30*60
COUNT_TO_GENERATE = 20


class RichHideMyEmail(HideMyEmail):
    _cookie_file = "cookie.txt"

    def __init__(self):
        super().__init__()
        self.console = Console()
        self.table = Table()

        if os.path.exists(self._cookie_file):
            # load in a cookie string from file
            with open(self._cookie_file, "r") as f:
                self.cookies = [line for line in f if not line.startswith("//")][0]
        else:
            self.console.log(
                '[bold yellow][WARN][/] No "cookie.txt" file found! Generation might not work due to unauthorized access.'
            )

    async def _generate_one(self) -> Union[str, None]:
        # First, generate an email
        gen_res = await self.generate_email()

        if not gen_res:
            return
        elif "success" not in gen_res or not gen_res["success"]:
            error = gen_res["error"] if "error" in gen_res else {}
            err_msg = "Unknown"
            if type(error) == int and "reason" in gen_res:
                err_msg = gen_res["reason"]
            elif type(error) == dict and "errorMessage" in error:
                err_msg = error["errorMessage"]
            self.console.log(
                f"[bold red][ERR][/] - Failed to generate email. Reason: {err_msg}"
            )
            return

        email = gen_res["result"]["hme"]
        self.console.log(f'[50%] "{email}" - Successfully generated')

        # Then, reserve it
        reserve_res = await self.reserve_email(email)

        if not reserve_res:
            return
        elif "success" not in reserve_res or not reserve_res["success"]:
            error = reserve_res["error"] if "error" in reserve_res else {}
            err_msg = "Unknown"
            if type(error) == int and "reason" in reserve_res:
                err_msg = reserve_res["reason"]
            elif type(error) == dict and "errorMessage" in error:
                err_msg = error["errorMessage"]
            self.console.log(
                f'[bold red][ERR][/] "{email}" - Failed to reserve email. Reason: {err_msg}'
            )
            return

        self.console.log(f'[100%] "{email}" - Successfully reserved')
        return email

    async def _generate(self, num: int):
        tasks = []
        for _ in range(num):
            task = asyncio.ensure_future(self._generate_one())
            tasks.append(task)

        return filter(lambda e: e is not None, await asyncio.gather(*tasks))

    async def ask_action(self):
        try:
            self.console.rule()
            s = Prompt.ask(
                "1. Generate emails\n"
                "2. Get emails list\n"
                "\n"
                "[bold green]Select your action [cyan](Ctrl+C to exit)[reset]",
                console=self.console
            ).strip()

            if s == "1":
                return await self.generate()
            elif s == "2":
                return await self.list(True, )
            else:
                raise ValueError
        except (KeyboardInterrupt, ValueError):
            return

    async def generate(self) -> List[str]:
        try:
            self.console.rule()
            with self.console.status(f"[bold green]Generating iCloud emails..."):
                while True:
                    count = int(COUNT_TO_GENERATE)
                    emails = []
                    while count > 0:
                        batch = await self._generate(MAX_CONCURRENT_TASKS)
                        emails += batch
                        count -= MAX_CONCURRENT_TASKS
                    self.console.log(f"[cyan]Generated {len(emails)}, sleeping {round(SLEEP_INTERVAL/60)} minute(s)")
                    await asyncio.sleep(SLEEP_INTERVAL)
        except KeyboardInterrupt:
            return []

    async def list(self, active: bool, search: str = None) -> None:
        self.console.rule()
        with self.console.status(f"[bold green]Getting iCloud emails..."):
            gen_res = await self.list_email()
        if not gen_res:
            return

        if "success" not in gen_res or not gen_res["success"]:
            error = gen_res["error"] if "error" in gen_res else {}
            err_msg = "Unknown"
            if type(error) == int and "reason" in gen_res:
                err_msg = gen_res["reason"]
            elif type(error) == dict and "errorMessage" in error:
                err_msg = error["errorMessage"]
            self.console.log(
                f"[bold red][ERR][/] - Failed to generate email. Reason: {err_msg}"
            )
            return

        self.table.add_column("Label")
        self.table.add_column("Hide my email")
        self.table.add_column("Creation Time")
        self.table.add_column("Status")

        email_strings = []
        for email in gen_res["result"]["hmeEmails"]:
            status = "Active" if email["isActive"] else "Inactive"
            creation_time = datetime.datetime.fromtimestamp(
                email["createTimestamp"] / 1000
            ).strftime("%Y-%m-%d %H:%M")
            email_strings.append(f"{email['label']};{email['hme']};{creation_time};{status}")
            if email["isActive"] == active:
                if search is None or re.search(search, email["label"]):
                    self.table.add_row(
                        email["label"],
                        email["hme"],
                        creation_time,
                        status,
                    )
        self.console.print(self.table)
        with open("emails.txt", "w") as f:
            f.write(os.linesep.join(email_strings))
        self.console.log('[bold green]Written to emails.txt in format [cyan]label;email;time;status')


async def generate() -> None:
    async with RichHideMyEmail() as hme:
        await hme.generate()


async def list(active: bool, search: str = None) -> None:
    async with RichHideMyEmail() as hme:
        await hme.list(active, search)


async def ask_action() -> None:
    async with RichHideMyEmail() as hme:
        await hme.ask_action()

if __name__ == "__main__":
    loop = asyncio.new_event_loop()
    try:
        loop.run_until_complete(ask_action())
    except KeyboardInterrupt:
        pass
