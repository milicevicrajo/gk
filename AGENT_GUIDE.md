# AGENT_GUIDE — Građevinska knjiga (GK) — MVT — FAZA 1

> Ovaj fajl je stalni vodič za agenta. Agent **uvek** prati ovaj dokument dok radi na kodu. U ovoj fazi implementira se skeleton projekta, modeli i minimalni MVT sloj — bez API‑ja, bez SPA, bez token‑overe i bez PDF‑a.

## 0) Kontekst
- Projekat: **gk** (Django project)
- App: **core**
- Arhitektura: **Django MVT**
- Baza: **SQLite** (za start), PostgreSQL kasnije
- UI: **Bootstrap 5**
- Uloge (grupe): `izvodjac`, `nadzor`, `investitor`, `admin`
- Pretpostavka: **jedan Project** u bazi (bez filtracije po projektu u ovoj fazi)

## 1) Ciljevi FAZE 1 (Definition of Done)
1. Napravljen Django projekat `gk` i app `core`; `core` dodat u `INSTALLED_APPS`.
2. Kreirani modeli sa migracijama:
   - `Project(name, code)`
   - `BoQItem(project, code, title, uom, contract_qty, unit_price)`
   - `GKSheet(project, number, period_from, period_to, status= draft|submitted|approved|rejected, created_by, submitted_at, approved_at)`
   - `GKEntry(sheet, boq_item, qty, note)`
   - *Napomena*: `ReviewToken` **se ne koristi** u FAZI 1, ali može postojati kao stub model u `models.py` (bez upotrebe).
3. Osnovne stranice i URL‑ovi (MVT):
   - `/sheets/` — lista listova (read)
   - `/sheets/new/` — kreiranje lista
   - `/sheets/<id>/` — detalj + inline formset za stavke
4. Template‑i:
   - `base.html` (Bootstrap 5 + prikaz `messages`)
   - `sheet_list.html`, `sheet_form.html`, `sheet_detail.html`
5. Dozvole (grupe): komanda `bootstrap_roles` kreira 4 grupe; u FAZI 1:
   - `izvodjac` može kreirati/menjati **svoje** listove kad su `draft`/`rejected`
   - `nadzor` i `investitor` read‑only
   - `admin` sve
6. Nema token‑overe, nema e‑mailova, nema PDF‑a — to dolazi u narednim fazama.
7. Projekat se podiže bez grešaka, osnovni tok (kreiraj → dodaj stavku → sačuvaj) radi.

## 2) Guardrails (pravila kojih se agent drži)
- **Bez DRF‑a i SPA‑a** u FAZI 1.
- Ne uvoditi nove biblioteke bez potrebe.
- Koristiti `login_required` i grupne provere za edit prava.
- Tekstovi u UI na srpskom.
- Kôd jasan, komentarisani delovi samo tamo gde je potrebno.
- Isporučiti **diff/patch** ili kompletne fajlove po traženju, bez suvišne naracije.
- Jedna logička migracija po grupi izmena.
- Testovi u FAZI 1 su minimalni (smoke) — opciono.

## 3) Struktura projekta (predlog)
```
gk/
  core/
    management/
      commands/
        bootstrap_roles.py
    templates/
      core/
        base.html
        sheet_list.html
        sheet_form.html
        sheet_detail.html
    __init__.py
    models.py
    forms.py
    views.py
    urls.py
    perms.py
  gk/
    settings.py
    urls.py
  manage.py
  AGENT_GUIDE.md  ← ovaj fajl
```

## 4) Komponente i zadaci za agenta

### 4.1 MODELI (core/models.py)
- `Project(name, code unique)`
- `BoQItem(project FK, code, title, uom, contract_qty Dec(16,3), unit_price Dec(16,2)); unique_together (project, code)`
- `GKSheet(project FK, number, period_from, period_to, status choices, created_by FK, submitted_at, approved_at); unique_together (project, number)`
- `GKEntry(sheet FK, boq_item FK, qty Dec(16,3), note Text); unique_together (sheet, boq_item)`
- `ReviewToken` stub klasa (bez upotrebe u FAZI 1) — opcionalno dodati sada ili kasnije.
- Kreirati migracije.

### 4.2 DOZVOLE (core/perms.py)
- Helper `user_in_group(user, name)`.
- U FAZI 1: `izvodjac` uređuje **samo svoje** listove u `draft/rejected`; ostali read‑only, `admin` sve.

### 4.3 FORME (core/forms.py)
- `GKSheetForm` (number, period_from, period_to)
- `GKEntryForm` (boq_item, qty, note)
- `GKEntryFormSet = inlineformset_factory(GKSheet, GKEntry, ...)`

### 4.4 VIEWS (core/views.py)
- `sheet_list` — lista listova, `login_required`.
- `sheet_create` — samo `izvodjac`; kreira list vezan za `Project.objects.first()` i `created_by = request.user`.
- `sheet_detail` — prikaz i edit (ako `can_edit`), sa `GKEntry` inline formsetom.
- Bez submit/approve/reject URL‑ova u FAZI 1.

### 4.5 URL‑ovi (core/urls.py + gk/urls.py)
- Povezati rute za list, create, detail; uključiti `core.urls` u `gk/urls.py`.

### 4.6 TEMPLATE‑i (templates/core/*.html)
- `base.html`: Bootstrap 5 preko CDN, blok za messages.
- `sheet_list.html`: tabela sa linkom “+ Novi list” (samo ako je user u grupi `izvodjac`).
- `sheet_form.html`: standardna forma za kreiranje.
- `sheet_detail.html`: forma + inline formset (ili read‑only prikaz ako nema prava).

### 4.7 Management komanda (bootstrap_roles)
- Kreira grupe: `izvodjac`, `nadzor`, `investitor`, `admin`.

## 5) .gitignore (osnovno)
- `venv/`, `.env`, `__pycache__/`, `*.pyc`, `.DS_Store`, `db.sqlite3`, `/media/`, `/staticfiles/`

## 6) Setup uputstvo (za ljude)
1. Kreiraj i aktiviraj venv  
   - Windows: `python -m venv venv && venv\Scripts\activate`  
   - Linux/Mac: `python -m venv venv && source venv/bin/activate`
2. Instaliraj: `pip install django==5.0 python-dotenv`
3. Inicijalizuj projekat: `django-admin startproject gk .`  
4. Napravi app: `python manage.py startapp core`
5. Dodaj `core` u `INSTALLED_APPS`; pokreni `python manage.py migrate`
6. Kreiraj superuser: `python manage.py createsuperuser`
7. Pokreni: `python manage.py runserver`
8. Kreiraj grupe: `python manage.py bootstrap_roles`

## 7) Granice FAZE 1 (Out of scope)
- Bez email‑a, token‑overe, PDF‑a, kumulativa i validacija po ugovoru.
- To dolazi u Fazi 2/3/4/5.

## 8) Konvencija commit poruka
```
<scope>: <kratak opis>
- podstavka 1
- podstavka 2
```
Primer:
```
core/models: dodati osnovne GK modele
- Project, BoQItem, GKSheet, GKEntry
- migracije i __str__ metode
```
