import json
import os
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich import box

console = Console()

SAVE_FILE = os.path.expanduser("~/Desktop/budget_data.json")


def save_data(data):
    with open(SAVE_FILE, "w") as f:
        json.dump(data, f)


def load_data():
    if os.path.exists(SAVE_FILE):
        with open(SAVE_FILE, "r") as f:
            return json.load(f)
    return None


def get_float(prompt):
    while True:
        try:
            raw = console.input(f"[bold cyan]{prompt}[/] ")
            return float(raw.replace("$", "").replace(",", ""))
        except ValueError:
            console.print("[red]Please enter a number.[/]")


def get_int(prompt):
    while True:
        try:
            return int(console.input(f"[bold cyan]{prompt}[/] "))
        except ValueError:
            console.print("[red]Please enter a whole number.[/]")


def get_goal():
    name = console.input("[bold cyan]What are you saving for?[/] ")
    cost = get_float(f"How much does {name} cost? $")
    monthly_payment = get_float("How much would the monthly payment be? $")
    num_payments = get_int("How many months would you pay for? ")
    return {"name": name, "cost": cost, "monthly_payment": monthly_payment, "num_payments": num_payments}


def time_string(months):
    if months < 1:
        return "Less than a month"
    elif months < 12:
        return f"{months:.1f} months"
    else:
        years = months / 12
        return f"{years:.1f} years ({months:.0f} months)"


def show_goal(goal, balance, monthly_income):
    name = goal["name"]
    cost = goal["cost"]
    monthly_payment = goal["monthly_payment"]
    num_payments = goal["num_payments"]
    needed = cost - balance

    if needed <= 0:
        console.print(Panel(f"[green]You already have enough to buy {name}![/]", title=f"[bold]{name}[/]"))
        return

    months_to_save = needed / monthly_income
    total_paid = monthly_payment * num_payments
    can_afford = monthly_income >= monthly_payment

    table = Table(box=box.ROUNDED, show_header=False, padding=(0, 2))
    table.add_column(style="bold yellow", width=22)
    table.add_column()

    table.add_row("Amount needed", f"[white]${needed:,.2f}[/]")
    table.add_section()

    table.add_row("[bold green]Save Up First[/]", "")
    table.add_row("  Time to save", f"[cyan]{time_string(months_to_save)}[/]")
    table.add_row("  Total cost", f"[white]${cost:,.2f}[/]")
    table.add_section()

    table.add_row("[bold magenta]Payment Plan[/]", "")
    table.add_row("  Monthly payment", f"[cyan]${monthly_payment:,.2f} x {num_payments} months[/]")
    table.add_row("  Total cost", f"[white]${total_paid:,.2f}[/]")

    if can_afford:
        leftover = monthly_income - monthly_payment
        table.add_row("  Leftover per month", f"[green]${leftover:,.2f}[/]")
    else:
        shortage = monthly_payment - monthly_income
        table.add_row("  Shortage per month", f"[red]-${shortage:,.2f}[/]")

    table.add_section()

    if not can_afford:
        verdict = f"[red]Payment plan not affordable. Save up in {time_string(months_to_save)}.[/]"
    elif total_paid > cost:
        extra = total_paid - cost
        verdict = f"[yellow]Payment plan costs ${extra:,.2f} more. Saving up takes {time_string(months_to_save)} but costs less.[/]"
    else:
        verdict = f"[green]Payment plan costs the same as paying upfront — get it now if you want.[/]"

    table.add_row("[bold]Verdict[/]", verdict)

    console.print(Panel(table, title=f"[bold white]{name}[/]", border_style="bright_blue"))


def main():
    console.print(Panel("[bold white]Savings Goal Calculator[/]", style="bold bright_blue", padding=(1, 4)))

    saved = load_data()

    if saved:
        console.print("[green]Loaded your saved goals.[/]\n")
        balance = get_float("What is your current balance? $")
        monthly_income = get_float("How much money do you receive per month? $")
        monthly_expenses = get_float("How much do you spend per month on expenses? $")
        spendable = monthly_income - monthly_expenses

        goals = saved["goals"]
        console.print(f"\n[bold yellow]You have {len(goals)} saved goal(s). Add more or go straight to results.[/]")
        another = console.input("[bold cyan]Add a new goal? (yes/no)[/] ").strip().lower()
        while another == "yes":
            console.print(f"\n[bold yellow]Goal {len(goals) + 1}[/]")
            goals.append(get_goal())
            another = console.input("\n[bold cyan]Add another goal? (yes/no)[/] ").strip().lower()
    else:
        balance = get_float("What is your current balance? $")
        monthly_income = get_float("How much money do you receive per month? $")
        monthly_expenses = get_float("How much do you spend per month on expenses? $")
        spendable = monthly_income - monthly_expenses

        goals = []
        while True:
            console.print(f"\n[bold yellow]Goal {len(goals) + 1}[/]")
            goals.append(get_goal())
            another = console.input("\n[bold cyan]Add another goal? (yes/no)[/] ").strip().lower()
            if another != "yes":
                break

    save_data({"goals": goals})
    console.print("[dim]Progress saved.[/]")

    console.print("\n")
    console.rule("[bold bright_blue]YOUR GOALS[/]")
    console.print()

    for goal in goals:
        show_goal(goal, balance, spendable)
        console.print()


if __name__ == "__main__":
    main()
