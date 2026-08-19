# Netback Calculator — Architecture technique

**Objectif du document** : brief de conception complet, à donner tel quel (ou par sections) à Claude Fable 5 pour exécuter le build. Rien ici ne nécessite de données de marché live ni de décision de recrutement finale : c'est un moteur de calcul et une app de démonstration, conçus pour être crédibles techniquement et extensibles.

---

## 1. Objectif & principes de conception

**Ce que fait l'outil** : à partir d'un prix de vente (CIF/DES/DAP à destination), remonter au prix FOB net-back au port de chargement en déduisant fret, assurance, coût de financement, frais portuaires et ajustements qualité. Et inversement : à partir d'un prix FOB, calculer le coût rendu (landed cost) pour un acheteur donné.

**Principes** :
- **Commodity-agnostic par construction.** Le moteur de calcul ne connaît rien de spécifique à une matière première. Chaque commodité est un profil de configuration (unité, paramètres qualité, formule d'ajustement) injecté dans le moteur, pas du code en dur.
- **Séparation stricte calcul / données / présentation.** Le moteur (`core/`) ne fait aucun appel réseau et ne dépend d'aucune donnée live. La couche données (`data/`) est derrière une interface abstraite, remplaçable sans toucher au moteur. L'app Streamlit ne fait que de l'orchestration UI.
- **Testable dès le premier commit.** Chaque module de coût est une fonction pure (inputs → output numérique), donc testable unitairement avec des cas de référence connus.
- **Ce qui est repoussé reste un point d'extension, pas un trou.** Les prix/fret live ne sont pas codés maintenant, mais l'interface qui les recevra existe et est mockée avec des données statiques crédibles.

**Commodité de référence pour l'implémentation v1** : bauxite (vrac sec, export Guinée), avec le lithium (concentré de spodumène) comme deuxième profil pour prouver l'extensibilité. Ce choix s'aligne avec le narratif Afrique/ressources critiques déjà construit (capstone Glencore/Guinée, thèse nucléaire/uranium, DCA lithium). Le moteur reste générique : changer de commodité est une question de config, pas de code.

---

## 2. Vue d'ensemble fonctionnelle

Deux modes de calcul, tous deux exposés dans l'app :

1. **Mode netback (backward)** : Prix de vente CIF → déductions → FOB net-back équivalent. C'est le calcul que fait un trader pour comparer plusieurs débouchés et choisir le plus rentable.
2. **Mode landed cost (forward)** : Prix FOB → additions → coût rendu CIF/DAP pour un acheteur. C'est le calcul qu'un acheteur fait pour comparer plusieurs origines.

Les deux modes partagent exactement les mêmes modules de coût ; seule la direction du calcul change (addition vs soustraction), ce qui est un argument de conception à mettre en avant à l'oral (un seul moteur, deux vues).

---

## 3. Modèle de données

Schémas de base (à implémenter en `dataclasses` ou `pydantic` selon préférence — pydantic recommandé pour la validation gratuite dans l'app Streamlit).

```python
# models/schemas.py

class CommodityProfile:
    name: str                      # "Bauxite", "Spodumene concentrate"
    unit: str                      # "dmt" (dry metric tonne), "wmt", "mt"
    benchmark_spec: dict           # ex. {"Al2O3": 49.0, "SiO2": 5.0} pour bauxite
    quality_adjustment_fn: str     # référence vers la fonction d'ajustement à utiliser

class Route:
    load_port: str
    discharge_port: str
    distance_nm: float             # milles nautiques
    transit_days: float
    vessel_type: str               # "Handysize", "Panamax", "Capesize"...

class CostInputs:
    quantity: float
    price_basis: float             # prix d'entrée (CIF ou FOB selon le mode)
    freight_rate_per_unit: float   # $/tonne, vient du data layer
    insurance_rate_pct: float      # % appliqué à la valeur assurée
    financing_rate_annual_pct: float  # coût du capital annualisé
    payment_terms_days: float      # jours de crédit acheteur/fournisseur
    load_port_fee_per_unit: float
    discharge_port_fee_per_unit: float
    actual_quality: dict           # valeurs qualité réelles du lot
    commission_pct: float = 0.0    # commission trader, optionnelle

class NetbackResult:
    mode: str                      # "netback" | "landed_cost"
    base_price: float
    freight_cost: float
    insurance_cost: float
    financing_cost: float
    port_fees_total: float
    quality_adjustment: float      # peut être positif ou négatif
    commission_cost: float
    result_price: float            # FOB net-back OU landed cost final
    breakdown: list[tuple[str, float]]  # pour le waterfall chart
```

Ce modèle est volontairement plat et explicite : chaque ligne du `breakdown` correspond à une barre du waterfall chart dans l'app.

---

## 4. Moteur de calcul (core)

Chaque module est une fonction pure dans son propre fichier, avec sa propre suite de tests. Aucun module n'importe Streamlit ni la couche données directement — tout est injecté en paramètres.

### 4.1 Fret (`core/freight.py`)

```
freight_cost = quantity × freight_rate_per_unit
```

Le taux (`freight_rate_per_unit`) vient du data layer (table statique v1). Le module lui-même ne fait que multiplier — la complexité (Worldscale, ajustement par taille de navire) reste dans le data layer, pas dans le core, pour garder le calcul central simple et auditable.

### 4.2 Assurance (`core/insurance.py`)

Convention standard du marché (Institute Cargo Clauses) : la valeur assurée = 110 % de la valeur CIF.

```
insured_value = (base_price + freight_cost) × 1.10
insurance_cost = insured_value × insurance_rate_pct
```

### 4.3 Coût de financement (`core/financing.py`)

Coût du capital immobilisé pendant le transit + les termes de paiement.

```
days_exposed = route.transit_days + payment_terms_days
financing_cost = (base_price × quantity) × (financing_rate_annual_pct / 365) × days_exposed
```

### 4.4 Frais portuaires (`core/port_fees.py`)

```
port_fees_total = quantity × (load_port_fee_per_unit + discharge_port_fee_per_unit)
```

### 4.5 Ajustement qualité/spec (`core/quality_adjustment.py`)

Module pluggable par commodité — c'est le seul endroit où la logique dépend de la matière première. Pattern : un registre de fonctions, une par `CommodityProfile.quality_adjustment_fn`.

Exemple pour la bauxite (ajustement linéaire par unité de déviation, pattern standard des indices Platts/CRU) :

```
adjustment = (actual["Al2O3"] - benchmark["Al2O3"]) × price_per_unit_alumina
           - max(0, actual["SiO2"] - benchmark["SiO2"]) × penalty_per_unit_silica
```

Pour un deuxième profil (lithium), la fonction change mais la signature reste identique : `(actual: dict, benchmark: dict, params: dict) -> float`. C'est ce qui prouve l'extensibilité sans réécrire le moteur.

### 4.6 Orchestrateur netback (`core/netback.py`)

Combine tous les modules ci-dessus dans les deux directions.

```
def compute_netback(inputs: CostInputs, route: Route, profile: CommodityProfile) -> NetbackResult:
    freight = freight_cost(...)
    insurance = insurance_cost(...)
    financing = financing_cost(...)
    ports = port_fees_total(...)
    quality = quality_adjustment(...)

    result = base_price - freight - insurance - financing - ports - commission + quality
    # (signe inversé en mode landed_cost : additions au lieu de soustractions)

    return NetbackResult(breakdown=[...], result_price=result, ...)
```

L'orchestrateur est le seul module testé de bout en bout avec des cas complets (voir section 8).

---

## 5. Couche données (data layer)

Interface abstraite + implémentation statique maintenant, stub live pour plus tard. C'est la partie de l'architecture qui absorbe tout le travail repoussé sans bloquer le reste.

```python
# data/providers/base.py
class PriceDataProvider(ABC):
    @abstractmethod
    def get_freight_rate(self, route: Route) -> float: ...
    @abstractmethod
    def get_benchmark_price(self, commodity: str) -> float: ...

# data/providers/static.py
class StaticDataProvider(PriceDataProvider):
    # lit des fichiers de référence dans data/reference/ (JSON/CSV)
    # tables : distances/temps de transit par route, frais portuaires par port,
    # taux de fret indicatifs par type de navire, specs benchmark par commodité

# data/providers/live.py
class LiveDataProvider(PriceDataProvider):
    # STUB uniquement en v1 : lève NotImplementedError avec un message clair
    # sera branché plus tard sur une source (Platts, Baltic Exchange, etc.)
```

**Données de référence statiques à préparer (`data/reference/`)** : une table de ports (frais indicatifs de chargement/déchargement), une table de distances/temps de transit pour 4-5 routes plausibles bauxite (Guinée → Chine, Guinée → Europe...), des taux de fret indicatifs par type de navire, et les specs benchmark bauxite/lithium. Chiffres approximatifs mais réalistes, avec sources citées en commentaire — l'objectif est la cohérence interne du modèle, pas l'exactitude au jour près (c'est justement ce qui sera branché en live plus tard).

---

## 6. Application Streamlit

Structure multi-pages, sidebar pour les inputs, corps de page pour les résultats.

- **Home** : présentation courte de l'outil, choix du mode (netback / landed cost), lien vers les autres pages.
- **Calculateur** (page principale) : sidebar avec sélection commodité, route, quantité, et tous les inputs de coût (avec valeurs par défaut pré-remplies depuis le `StaticDataProvider`, modifiables). Corps de page : résultat final en évidence + **waterfall chart** (bridge chart) montrant la décomposition prix de vente → chaque déduction → FOB net-back. Le waterfall est l'élément visuel le plus parlant pour un recruteur — c'est la représentation naturelle d'un netback.
- **Comparaison de scénarios** : permet de dupliquer 2-3 configurations (routes ou qualités différentes) et de les comparer côte à côte sur le netback obtenu. C'est ce qui démontre l'usage réel en trading (arbitrage entre débouchés).
- **Méthodologie** : page texte expliquant les formules et les hypothèses (utile pour un entretien — montre que ce n'est pas une boîte noire).

Librairies : `streamlit`, `plotly` (waterfall chart natif via `go.Waterfall`), `pydantic` pour la validation des inputs.

---

## 7. Structure du repo

```
netback-calculator/
├── README.md
├── LICENSE (MIT)
├── pyproject.toml
├── .gitignore
├── src/
│   └── netback/
│       ├── __init__.py
│       ├── core/
│       │   ├── freight.py
│       │   ├── insurance.py
│       │   ├── financing.py
│       │   ├── port_fees.py
│       │   ├── quality_adjustment.py
│       │   └── netback.py
│       ├── models/
│       │   └── schemas.py
│       ├── data/
│       │   ├── providers/
│       │   │   ├── base.py
│       │   │   ├── static.py
│       │   │   └── live.py
│       │   └── reference/
│       │       ├── ports.json
│       │       ├── routes.json
│       │       ├── freight_rates.json
│       │       └── commodity_specs.json
│       └── utils/
│           └── conversions.py
├── app/
│   ├── Home.py
│   └── pages/
│       ├── 1_Calculateur.py
│       ├── 2_Comparaison_scenarios.py
│       └── 3_Methodologie.py
├── tests/
│   ├── test_freight.py
│   ├── test_insurance.py
│   ├── test_financing.py
│   ├── test_port_fees.py
│   ├── test_quality_adjustment.py
│   ├── test_netback.py
│   └── fixtures/
│       └── reference_cases.json
└── docs/
    └── methodology.md
```

README à structurer classiquement : one-liner, capture d'écran du waterfall, quickstart (`pip install -e .`, `streamlit run app/Home.py`), architecture (renvoi vers ce document ou version résumée), roadmap ("live data integration planned").

---

## 8. Tests

`pytest`, un fichier de test par module du core + un fichier d'intégration pour l'orchestrateur.

Chaque test unitaire de module compare contre un cas calculé à la main (valeurs rondes, faciles à vérifier). Le test d'intégration (`test_netback.py`) prend un cas complet bauxite avec toutes les valeurs connues et vérifie que le `result_price` final tombe sur le chiffre attendu à 2 décimales près — c'est le test qui donne confiance dans l'orchestrateur.

Cible : couverture proche de 100 % sur `core/`, pas nécessaire sur `app/` (UI, peu testable unitairement de façon rentable).

---

## 9. Répartition du travail avec le crédit Fable 5

Découpage en sessions indépendantes, chacune livrable et testable avant de passer à la suivante. Donner ce document en entier comme contexte à chaque session, en précisant à chaque fois le périmètre exact.

1. **Session 1 — Core + modèles.** Implémenter `models/schemas.py` et les 5 modules de `core/` + `netback.py`, avec les tests unitaires et le test d'intégration. Rien d'autre (pas de Streamlit, pas de data layer réelle — inputs de test en dur dans les fixtures). Livrable : `core/` entièrement testé, `pytest` vert.
2. **Session 2 — Data layer.** Implémenter `base.py`, `static.py`, `live.py` (stub), et les fichiers de référence JSON pour bauxite (et lithium si le temps le permet). Livrable : `StaticDataProvider` capable d'alimenter tous les inputs de `CostInputs` pour une route bauxite donnée.
3. **Session 3 — App Streamlit.** Les 4 pages, connectées au core + data layer des sessions précédentes, avec le waterfall chart Plotly. Livrable : app qui tourne en local (`streamlit run`) de bout en bout.
4. **Session 4 — Finition repo.** README complet, `docs/methodology.md`, nettoyage, `pyproject.toml`, licence, premier commit propre + push GitHub. Optionnel : GitHub Actions pour lancer `pytest` sur chaque push (bon signal pour un recruteur qui regarde le repo).

**Consigne à donner explicitement à Fable 5 à chaque session** : ne pas anticiper l'intégration de données live, ne pas ajouter de clés d'API, rester strictement dans le périmètre de la session en cours. L'objectif de ce découpage est de garder chaque session courte et le crédit utilisé efficacement.

---

## 10. Ce qui reste repoussé (à ne pas construire maintenant)

- Prix de marché et taux de fret live (API Platts, Baltic Exchange ou équivalent) — juste l'interface `LiveDataProvider` en stub.
- Choix final du corridor/de la commodité pour coller à un rôle cible précis — la bauxite/Guinée est un exemple de démonstration, pas un engagement.
- Polish du narratif d'entretien (comment présenter le projet) — à travailler au moment où il sert réellement (candidature Singapour/INSEAD ou entretiens).
