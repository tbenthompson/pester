"""
This little app is split into two parts:
1. The menu bar app which runs the timers.
2. The check in window which grabs your note and stores it.
"""
import os
import sys
import datetime
import logging

from screeninfo import get_monitors
import tkinter as tk
import rumps
import multiprocessing

## Configuration!
debug = False
quick_filename = "~/.pester.txt"
quick_interval = 60 * 8  # in seconds
slow_directory = "~/obsidian/tbent/weekly/"
slow_interval = 60 * 60
min_words = 15
# The get_slow_filename function can be used for more complicated logic for
# where to store the messages.
def get_slow_filename():
    last_sunday = get_last_sunday_str()
    return os.path.join(slow_directory, f"week-{last_sunday}.md")

# Handy debugging configuration that makes things happen fast!
debug = True
if debug:
    quick_filename = "./debug.txt"
    quick_interval = 15
    slow_directory = "./"
    slow_interval = 40
    rumps.debug_mode(True)
    min_words = 2

logging.basicConfig(
    format="%(asctime)s %(levelname)s %(message)s",
    level=logging.DEBUG,
    stream=sys.stdout,
)

logger = logging.getLogger()


class Window:
    def __init__(self, root, tk_obj, m, quick):
        self.root = root

        self.tk_obj = tk_obj
        self.tk_obj.resizable(False, False)

        win_width = 600
        win_height = 300
        win_x = m.x + m.width // 2 - win_width // 2
        win_y = m.height // 2 - win_height // 2
        geom_spec = f"{win_width}x{win_height}+{win_x}+{win_y}"
        logger.info(f"opening window with geometry: {geom_spec}")
        self.tk_obj.geometry(geom_spec)

        self.quick = quick
        if quick:
            message = "Quick check in."
        else:
            message = f"Detailed check in. Please write at least {min_words} words."

        l = tk.Label(self.tk_obj, text=message)
        self.inputtxt = tk.Text(self.tk_obj, height=10, width=25)
        self.tk_obj.bind("<Return>", self.record)
        l.pack()
        self.inputtxt.pack()
        self.inputtxt.focus_set()

    def record(self, event):
        txt = self.inputtxt.get("1.0", "end-1c")
        if not self.quick:
            if len(txt.split()) < min_words:
                return
        logger.info(f"recording text {txt}")

        if self.quick:
            # append to quick file.
            logger.info(f"writing to {quick_filename}")
            with open(quick_filename, "a+") as f:
                f.write(f"{get_full_timestamp()} contents={txt}")
        else:
            # prepend to slow weekly file.
            slow_filename = get_slow_filename()
            mode = "r+" if os.path.exists(slow_filename) else "w+"
            logger.info(f"writing to {slow_filename}")
            with open(slow_filename, mode) as f:
                contents = f.read()
                f.seek(0)
                f.write(txt)
                f.write(contents)

        self.root.destroy()


def get_full_timestamp():
    return f"{datetime.datetime.now():%Y-%m-%d %H:%M:%S}"


def get_last_sunday_str():
    today = datetime.date.today()
    idx = (today.weekday() + 1) % 7
    sun = today - datetime.timedelta(idx)
    sun_str = f"{sun:%Y-%m-%d}"
    return sun_str


def ask(quick):
    root = tk.Tk()
    windows = []
    for i, m in enumerate(get_monitors()):
        logging.info(f"opening asker window on monitor {i}")
        if i == 0:
            win = root
        else:
            # build a top level node as a child of the current node. This will
            # work regardless of whether the current node is a root or toplevel.
            win = tk.Toplevel(win)

        windows.append(Window(root, win, m, quick))
    root.mainloop()


def launch_asker(quick):
    # print('hi')
    ask(quick)

class SkipFirstTimer(rumps.Timer):
    def __init__(self, callback, interval):
        self.orig_callback = callback
        super().__init__(self.callback_wrapper, interval)
    
    def callback_wrapper(self, timer):
        if self.skip:
            self.skip = False
            return
        self.orig_callback(timer)

    def start(self):
        self.skip = True
        super().start()

class Pester(rumps.App):
    def __init__(self):
        # icon from https://www.flaticon.com/uicons?word=strawberry
        super().__init__("Awesome App", icon="strawberry.png", template=True)
        self.quick_timer = SkipFirstTimer(lambda timer: self.ask(True), quick_interval)
        self.slow_timer = SkipFirstTimer(lambda timer: self.ask(False), slow_interval)
        self.pause_timer = SkipFirstTimer(lambda timer: self.toggle_timers(), slow_interval)
        self.toggle_timers()
        self.asking = False

    @rumps.clicked("Pause one hour")
    def pause_resume(self, sender):
        sender.title = "Pause" if sender.title == "Resume" else "Resume"
        self.toggle_timers()

    def toggle_timers(self):
        if not self.quick_timer.is_alive():
            assert(not self.slow_timer.is_alive())
            self.quick_timer.start()
            self.slow_timer.start()
            self.pause_timer.stop()
        else:
            assert(self.slow_timer.is_alive())
            self.quick_timer.stop()
            self.slow_timer.stop()
            self.pause_timer.start()

    @rumps.clicked("Quick")
    def quick(self, _):
        self.ask(True)

    @rumps.clicked("Slow")
    def slow(self, _):
        self.ask(False)

    def ask(self, quick):
        # skip if an ask is already happening, do I need to worry about
        # multithreadedness with the timer threads? mutex here? not a disaster
        # if two windows pop up!
        if self.asking:
            logger.info('skipping ask because another ask is ongoing')
            return

        self.asking = True
        # tkinter and rumps conflict between they both use cocoa behind the scenes.
        # the easiest solution is to just launch a separate process.
        p = multiprocessing.Process(target=launch_asker, args=(quick,))
        p.start()
        p.join()
        self.asking = False


def main():
    logger.info("launching menu bar app")
    Pester().run()


if __name__ == "__main__":
    main()
