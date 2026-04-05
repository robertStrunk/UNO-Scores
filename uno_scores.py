"""
UNO hand tracker — records each hand to a CSV:
Date, player scores (only the winner gets points for that row), and an optional comment.
Comments are written with the csv module so commas, quotes, and newlines do not break the file.
"""

from __future__ import annotations

import csv
import re
import tkinter as tk
from datetime import date, datetime
from pathlib import Path
from tkinter import messagebox, ttk

DATA_FILE = Path(__file__).resolve().parent / "uno_scores.csv"
DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def parse_iso_date(s: str) -> date | None:
    s = s.strip()
    if not DATE_RE.match(s):
        return None
    try:
        return datetime.strptime(s, "%Y-%m-%d").date()
    except ValueError:
        return None


def ensure_header(path: Path, headers: list[str]) -> None:
    if path.exists() and path.stat().st_size > 0:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(headers)


def read_rows(path: Path) -> list[list[str]]:
    if not path.exists():
        return []
    with path.open(newline="", encoding="utf-8") as f:
        return list(csv.reader(f))


def sanitize_csv_cell(value: str) -> str:
    """Remove NULs; other special characters are safe when using csv.writer quoting."""
    return value.replace("\x00", "")


def pad_row_to_length(row: list[str], length: int) -> list[str]:
    r = list(row)
    if len(r) >= length:
        return r[:length]
    return r + [""] * (length - len(r))


def migrate_csv_add_comment_column(path: Path, old_header: list[str], new_header: list[str]) -> None:
    """Upgrade a 4-column file to include a Comment column; preserves data via csv.reader/writer."""
    rows = read_rows(path)
    if not rows:
        return
    header, *data = rows
    if len(header) != 4 or header != old_header or len(new_header) != 5:
        return
    out = [new_header] + [pad_row_to_length(r, 5) for r in data]
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerows(out)


class UnoScoresApp(tk.Tk):
    COMMENT_HEADER = "Comment"

    # initialize the app
    def __init__(self) -> None:
        super().__init__()
        self.title("UNO Game")
        self.minsize(420, 520)
        self.geometry("560x620")

        self.player_names = ["Dad", "Luke", "Jake"]
        self.winner_var = tk.IntVar(value=0)
        self.points_var = tk.StringVar(value="")
        self.date_var = tk.StringVar(value=date.today().isoformat())

        self._build_ui()

    def _csv_headers(self) -> list[str]:
        return [
            "Date",
            self._player_label(0),
            self._player_label(1),
            self._player_label(2),
            self.COMMENT_HEADER,
        ]

    def _build_ui(self) -> None:
        pad = {"padx": 12, "pady": 6}

        frm = ttk.Frame(self, padding=16)
        frm.pack(fill=tk.BOTH, expand=True)

        ttk.Label(frm, text="Hand winner").grid(row=5, column=0, sticky="ne", **pad)
        win_frame = ttk.Frame(frm)
        win_frame.grid(row=5, column=1, sticky="w", **pad)

        for i in range(3):
            ttk.Radiobutton(
                win_frame,
                text=self.player_names[i],
                variable=self.winner_var,
                value=i,
            ).pack(anchor="w")

        ttk.Label(frm, text="Points (winner)").grid(row=6, column=0, sticky="e", **pad)
        ttk.Entry(frm, textvariable=self.points_var, width=12).grid(row=6, column=1, sticky="w", **pad)

        ttk.Label(frm, text="Date (YYYY-MM-DD)").grid(row=7, column=0, sticky="e", **pad)
        ttk.Entry(frm, textvariable=self.date_var, width=14).grid(row=7, column=1, sticky="w", **pad)

        ttk.Label(frm, text="Comment (optional)").grid(row=8, column=0, sticky="ne", **pad)
        self.comment_text = tk.Text(frm, height=3, width=42, wrap=tk.WORD)
        self.comment_text.grid(row=8, column=1, sticky="ew", **pad)

        btn_row = ttk.Frame(frm)
        btn_row.grid(row=9, column=0, columnspan=2, pady=12)
        ttk.Button(btn_row, text="Save hand to file", command=self._save_hand).pack(side=tk.LEFT, padx=4)
        ttk.Button(btn_row, text="Refresh totals", command=self._refresh_view).pack(side=tk.LEFT, padx=4)

        ttk.Label(frm, text=f"Data file: {DATA_FILE}").grid(row=10, column=0, columnspan=2, sticky="w", **pad)

        ttk.Label(frm, text="Running totals").grid(row=11, column=0, columnspan=2, sticky="w", **pad)
        self.totals_text = tk.Text(frm, height=4, width=56, state=tk.DISABLED, wrap=tk.WORD)
        self.totals_text.grid(row=12, column=0, columnspan=2, sticky="ew", **pad)

        ttk.Label(frm, text="Recent hands (from file)").grid(row=13, column=0, columnspan=2, sticky="w", **pad)
        tree_frame = ttk.Frame(frm)
        tree_frame.grid(row=14, column=0, columnspan=2, sticky="nsew", **pad)
        frm.rowconfigure(14, weight=1)
        frm.columnconfigure(1, weight=1)

        self.tree = ttk.Treeview(
            tree_frame, columns=("d", "p1", "p2", "p3", "cmt"), show="headings", height=8
        )

        for cid, h, w in (
            ("d", "Date", 88),
            ("p1", "P1", 44),
            ("p2", "P2", 44),
            ("p3", "P3", 44),
            ("cmt", "Comment", 200),
        ):
            self.tree.heading(cid, text=h)
            self.tree.column(cid, width=w, stretch=True)

        
        scroll = ttk.Scrollbar(tree_frame, orient=tk.VERTICAL, command=self.tree.yview)
        self.tree.configure(yscrollcommand=scroll.set)
        self.tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scroll.pack(side=tk.RIGHT, fill=tk.Y)

        self._refresh_view()

    def _player_label(self, index: int) -> str:
        v = self.player_names[index]
        raw = v.get() if hasattr(v, "get") else v
        s = str(raw).strip()
        return s or f"Player {index + 1}"

    def _refresh_view(self) -> None:
        rows = read_rows(DATA_FILE)
        for item in self.tree.get_children():
            self.tree.delete(item)

        if not rows:
            self._set_totals_text("No data yet. Save a hand to create the file.")
            self._sync_tree_headings(["Date", "P1", "P2", "P3", self.COMMENT_HEADER])
            return

        header, *data = rows
        self._sync_tree_headings(header)

        for r in reversed(data[-50:]):
            if len(r) < 4:
                continue
            self.tree.insert("", tk.END, values=pad_row_to_length(r, 5))

        totals = self._compute_totals(rows)
        names = self._display_names(header)
        lines = [f"{names[i]}: {totals[i]} points" for i in range(3)]
        self._set_totals_text("\n".join(lines))

    def _display_names(self, header: list[str]) -> list[str]:
        if len(header) >= 4:
            return [header[1], header[2], header[3]]
        return [self._player_label(i) for i in range(3)]

    def _sync_tree_headings(self, cols: list[str]) -> None:
        default = ("Date", "P1", "P2", "P3", self.COMMENT_HEADER)
        if len(cols) >= 4:
            labels = list(cols[:4])
            labels.append(cols[4] if len(cols) >= 5 else self.COMMENT_HEADER)
        else:
            labels = list(default)
        for cid, text in zip(("d", "p1", "p2", "p3", "cmt"), labels):
            self.tree.heading(cid, text=text)

    def _compute_totals(self, rows: list[list[str]]) -> list[int]:
        total = [0, 0, 0]
        if len(rows) < 2:
            return total
        for r in rows[1:]:
            if len(r) < 4:
                continue
            for i in range(3):
                try:
                    total[i] += int(float(r[i + 1].strip()))
                except (ValueError, AttributeError):
                    pass
        return total

    def _set_totals_text(self, s: str) -> None:
        self.totals_text.configure(state=tk.NORMAL)
        self.totals_text.delete("1.0", tk.END)
        self.totals_text.insert(tk.END, s)
        self.totals_text.configure(state=tk.DISABLED)

    def _save_hand(self) -> None:
        d = parse_iso_date(self.date_var.get())
        if d is None:
            messagebox.showerror("Invalid date", "Use YYYY-MM-DD (e.g. 2026-04-05).")
            return

        raw = self.points_var.get().strip()
        try:
            points = int(raw)
        except ValueError:
            messagebox.showerror("Invalid points", "Enter a whole number of points.")
            return
        if points < 0:
            messagebox.showerror("Invalid points", "Points cannot be negative.")
            return

        comment_raw = self.comment_text.get("1.0", "end-1c")
        comment = sanitize_csv_cell(comment_raw)

        headers = self._csv_headers()
        ensure_header(DATA_FILE, headers)

        existing = read_rows(DATA_FILE)
        if existing and len(existing[0]) == 4 and existing[0] == headers[:4]:
            migrate_csv_add_comment_column(DATA_FILE, existing[0], headers)
            existing = read_rows(DATA_FILE)

        if existing and existing[0] != headers:
            if not messagebox.askyesno(
                "Header mismatch",
                "Player names in the file differ from the form. Still append this row?\n"
                "(Columns stay as in the existing file.)",
            ):
                return

        w = self.winner_var.get()
        winner_label = self._player_label(w)
        comment_display = comment if comment else "(none)"
        if len(comment_display) > 200:
            comment_display = comment_display[:197] + "..."
        summary = (
            f"Winner: {winner_label}\n"
            f"Points: {points}\n"
            f"Date: {d.isoformat()}\n"
            f"Comment: {comment_display}\n\n"
            "Save this hand to the file?"
        )
        if not messagebox.askyesno("Confirm hand", summary):
            return

        p1 = p2 = p3 = 0
        if w == 0:
            p1 = points
        elif w == 1:
            p2 = points
        else:
            p3 = points

        row = [d.isoformat(), str(p1), str(p2), str(p3), comment]
        with DATA_FILE.open("a", newline="", encoding="utf-8") as f:
            csv.writer(f).writerow(row)

        self.points_var.set("")
        self.comment_text.delete("1.0", tk.END)
        self._refresh_view()
        messagebox.showinfo("Saved", "Hand saved to uno_scores.csv")


def main() -> None:
    app = UnoScoresApp()
    app.mainloop()


if __name__ == "__main__":
    main()
