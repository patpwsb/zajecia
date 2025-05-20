import sys
import os
import json
import shutil
import subprocess
from datetime import datetime
from pathlib import Path
from PyQt6.QtWidgets import QApplication, QWidget, QVBoxLayout, QHBoxLayout, QLineEdit, QPushButton, QTableWidget, QTableWidgetItem, QHeaderView, QMessageBox

# Ustalamy ścieżki
if getattr(sys, 'frozen', False):
    base_dir = os.path.dirname(sys.executable)
else:
    base_dir = os.path.dirname(os.path.realpath(__file__))

keys_dir = os.path.join(base_dir, 'keys')
config_path = os.path.join(base_dir, 'config')  # opcjonalny - nieużywany
keys_json_path = os.path.join(base_dir, 'keys.json')
shared_config_path = os.path.join(keys_dir, 'config')  # Wspólny plik konfiguracyjny

# Tworzenie potrzebnych folderów/plików
if not os.path.exists(keys_dir):
    os.makedirs(keys_dir)

if not os.path.exists(keys_json_path):
    with open(keys_json_path, 'w') as f:
        json.dump([], f)

# Funkcja generująca nowy klucz SSH
def generate_ssh_key(email, host, alias):
    if not email or not host or not alias:
        QMessageBox.warning(window, "Błąd", "Wszystkie pola muszą być wypełnione!")
        return

    key_name = f"id_ed25519_{alias}"
    key_path = os.path.join(keys_dir, key_name)

    if os.path.exists(key_path):
        QMessageBox.critical(window, "Błąd", f"Klucz o nazwie {key_name} już istnieje!")
        return

    try:
        subprocess.run(
            ["ssh-keygen", "-t", "ed25519", "-C", email, "-f", key_path, "-N", ""],
            check=True
        )
    except subprocess.CalledProcessError:
        QMessageBox.critical(window, "Błąd", "Nie udało się wygenerować klucza SSH.")
        return

    host_name = host.split('.')[0]
    config_entry = f"""
Host {host_name}-{alias}
    HostName {host}
    User git
    IdentityFile ~/.ssh/{key_name}
""".strip()

    if os.path.exists(shared_config_path):
        with open(shared_config_path, 'r') as f:
            existing_config = f.read()
    else:
        existing_config = ""

    if config_entry not in existing_config:
        with open(shared_config_path, 'a') as f:
            f.write("\n\n" + config_entry)

    key_metadata = {
        "key_name": key_name,
        "email": email,
        "hostname": host,
        "alias": alias,
        "key_path": key_path,
        "created": datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    }

    try:
        with open(keys_json_path, 'r') as f:
            keys_data = json.load(f)
    except json.JSONDecodeError:
        keys_data = []

    keys_data.append(key_metadata)

    with open(keys_json_path, 'w') as f:
        json.dump(keys_data, f, indent=4)

    update_table()


def copy_key_to_ssh():
    alias = alias_input.text().strip()
    if not alias:
        QMessageBox.warning(window, "Błąd", "Podaj alias do skopiowania.")
        return

    with open(keys_json_path, 'r') as f:
        keys_data = json.load(f)

    key_entry = next((k for k in keys_data if k['alias'] == alias), None)

    if not key_entry:
        QMessageBox.warning(window, "Błąd", f"Nie znaleziono aliasu {alias}.")
        return

    key_path = key_entry["key_path"]
    public_key_path = f"{key_path}.pub"
    destination = os.path.expanduser("~/.ssh/")

    if not os.path.exists(destination):
        os.makedirs(destination)

    try:
        shutil.copy(key_path, destination)
        shutil.copy(public_key_path, destination)

        if os.path.exists(shared_config_path):
            shutil.copy(shared_config_path, os.path.join(destination, "config"))

        QMessageBox.information(window, "Sukces", f"Pliki skopiowane do {destination}")
    except Exception as e:
        QMessageBox.critical(window, "Błąd", f"Nie udało się skopiować: {e}")


def delete_all():
    reply = QMessageBox.question(window, 'Usuwanie', 'Czy na pewno chcesz usunąć wszystkie klucze i pliki konfiguracyjne?', QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
    if reply == QMessageBox.StandardButton.Yes:
        for key in os.listdir(keys_dir):
            os.remove(os.path.join(keys_dir, key))

        if os.path.exists(shared_config_path):
            os.remove(shared_config_path)

        with open(keys_json_path, 'w') as f:
            json.dump([], f)

        update_table()
        QMessageBox.information(window, "Sukces", "Wszystkie dane zostały usunięte.")


def delete_alias():
    alias_to_delete = alias_input.text()
    if not alias_to_delete:
        QMessageBox.warning(window, "Błąd", "Nie podano aliasu do usunięcia.")
        return

    with open(keys_json_path, 'r') as f:
        keys_data = json.load(f)

    keys_data_to_delete = [key for key in keys_data if key['alias'] == alias_to_delete]

    if not keys_data_to_delete:
        QMessageBox.warning(window, "Błąd", f"Nie znaleziono aliasu {alias_to_delete}.")
        return

    for key in keys_data_to_delete:
        key_path = key['key_path']
        key_pub_path = f"{key_path}.pub"
        if os.path.exists(key_path):
            os.remove(key_path)
        if os.path.exists(key_pub_path):
            os.remove(key_pub_path)

    if os.path.exists(shared_config_path):
        with open(shared_config_path, 'r') as f:
            lines = f.readlines()

        host_prefix = f"Host {keys_data_to_delete[0]['hostname'].split('.')[0]}-{alias_to_delete}"
        new_lines = []
        skip = False
        for line in lines:
            if line.strip().startswith("Host ") and line.strip() == host_prefix:
                skip = True
                continue
            if skip and line.strip().startswith("Host "):
                skip = False
            if not skip:
                new_lines.append(line)

        with open(shared_config_path, 'w') as f:
            f.writelines(new_lines)

    keys_data = [key for key in keys_data if key['alias'] != alias_to_delete]

    with open(keys_json_path, 'w') as f:
        json.dump(keys_data, f, indent=4)

    update_table()
    QMessageBox.information(window, "Sukces", f"Alias {alias_to_delete} został usunięty.")


def show_config():
    if not os.path.exists(shared_config_path):
        QMessageBox.critical(window, "Błąd", "Plik config nie istnieje.")
        return

    with open(shared_config_path, 'r') as f:
        full_config = f.read()

    if not full_config.strip():
        QMessageBox.information(window, "Config SSH", "Plik config jest pusty.")
    else:
        QMessageBox.information(window, "Config SSH", full_config.strip())


def show_keys_json():
    with open(keys_json_path, 'r') as f:
        keys_data = json.load(f)

    if not keys_data:
        QMessageBox.critical(window, "Błąd", "Brak danych do wyświetlenia.")
        return

    json_content = json.dumps(keys_data, indent=4)
    QMessageBox.information(window, "keys.json", json_content)


def update_table():
    with open(keys_json_path, 'r') as f:
        try:
            keys_data = json.load(f)
        except json.JSONDecodeError:
            keys_data = []

    table.setRowCount(0)

    for key in keys_data:
        row_position = table.rowCount()
        table.insertRow(row_position)
        table.setItem(row_position, 0, QTableWidgetItem(key['key_name']))
        table.setItem(row_position, 1, QTableWidgetItem(key['hostname']))
        table.setItem(row_position, 2, QTableWidgetItem(key['alias']))
        table.setItem(row_position, 3, QTableWidgetItem(key['email']))


# GUI setup
app = QApplication(sys.argv)

app.setStyleSheet("""
    QWidget {
        background-color: #2e2e2e;
        color: white;
        font-size: 14px;
    }
    QLineEdit, QPushButton, QTableWidget {
        background-color: #444444;
        border: 1px solid #888888;
        color: white;
    }
    QPushButton:hover {
        background-color: #555555;
    }
    QTableWidget {
        color: white;
        border: 1px solid #888888;
    }
    QHeaderView::section {
        background-color: #333333;
        color: white;
        font-weight: bold;
    }
""")

window = QWidget()
window.setWindowTitle("SSH Key Manager")
layout = QVBoxLayout()

form_layout = QVBoxLayout()

email_input = QLineEdit()
email_input.setPlaceholderText("Email")
form_layout.addWidget(email_input)

host_input = QLineEdit()
host_input.setPlaceholderText("Host")
form_layout.addWidget(host_input)

alias_input = QLineEdit()
alias_input.setPlaceholderText("Alias/Użytkownik")
form_layout.addWidget(alias_input)

layout.addLayout(form_layout)

button_layout = QHBoxLayout()

generate_button = QPushButton("Generuj klucz")
generate_button.clicked.connect(lambda: generate_ssh_key(email_input.text(), host_input.text(), alias_input.text()))
button_layout.addWidget(generate_button)

copy_button = QPushButton("Kopiuj do ~/.ssh")
copy_button.clicked.connect(copy_key_to_ssh)
button_layout.addWidget(copy_button)

delete_all_button = QPushButton("Usuń wszystko")
delete_all_button.clicked.connect(delete_all)
button_layout.addWidget(delete_all_button)

delete_alias_button = QPushButton("Usuń alias")
delete_alias_button.clicked.connect(delete_alias)
button_layout.addWidget(delete_alias_button)

show_config_button = QPushButton("Pokaż config")
show_config_button.clicked.connect(show_config)
button_layout.addWidget(show_config_button)

show_keys_json_button = QPushButton("Pokaż keys.json")
show_keys_json_button.clicked.connect(show_keys_json)
button_layout.addWidget(show_keys_json_button)

layout.addLayout(button_layout)

table = QTableWidget()
table.setColumnCount(4)
table.setHorizontalHeaderLabels(["Nazwa Klucza", "Host", "Alias", "Email"])
table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)

layout.addWidget(table)

window.setLayout(layout)
update_table()
window.show()

sys.exit(app.exec())
