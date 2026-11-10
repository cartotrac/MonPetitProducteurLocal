"""Charge les catalogues de produits types par activité (idempotent).

Le catalogue historique reste classé « maraîcher » (activite par
défaut) ; cette commande crée les listes des autres activités
(arboriculture, élevage, fromagerie, ruches, brasserie) et repositionne
explicitement les produits existants en maraîcher. Elle complète aussi
l'emoji de tout produit type qui n'en a pas (recherche par mot-clé,
indépendante des accents et de la casse).

Usage :  python manage.py charger_catalogues_activites
"""
from decimal import Decimal
import unicodedata

from django.core.management.base import BaseCommand

from portal.models import Exploitant, Produit, ProduitStandard

# (nom, categorie, unite, emoji, saisons, prix_indicatif)
CATALOGUES = {
    Exploitant.Activite.ARBORICULTEUR: [
        ("Pomme", "Fruits", "KG", "🍎", ["automne", "hiver"], Decimal("2.80")),
        ("Pomme à jus", "Fruits", "KG", "🍎", ["automne"], Decimal("1.90")),
        ("Poire", "Fruits", "KG", "🍐", ["automne"], Decimal("3.20")),
        ("Pêche", "Fruits", "KG", "🍑", ["été"], Decimal("3.80")),
        ("Nectarine", "Fruits", "KG", "🍑", ["été"], Decimal("3.90")),
        ("Abricot", "Fruits", "KG", "🍑", ["été"], Decimal("4.50")),
        ("Cerise", "Fruits", "KG", "🍒", ["été"], Decimal("6.80")),
        ("Prune", "Fruits", "KG", "🫐", ["été"], Decimal("3.60")),
        ("Fraise", "Fruits", "BQ", "🍓", ["printemps", "été"], Decimal("4.20")),
        ("Framboise", "Fruits", "BQ", "🍓", ["été"], Decimal("4.50")),
        ("Myrtille", "Fruits", "BQ", "🫐", ["été"], Decimal("4.80")),
        ("Raisin", "Fruits", "KG", "🍇", ["automne"], Decimal("4.20")),
        ("Melon", "Fruits", "PC", "🍈", ["été"], Decimal("2.80")),
        ("Pastèque", "Fruits", "PC", "🍉", ["été"], Decimal("3.90")),
        ("Noix", "Fruits", "KG", "🌰", ["automne"], Decimal("6.50")),
        ("Noisette", "Fruits", "KG", "🌰", ["automne"], Decimal("7.00")),
        ("Jus de pomme", "Transformés", "PC", "🧃", [], Decimal("3.50")),
        ("Compote de pomme", "Transformés", "PC", "🥧", [], Decimal("3.80")),
    ],
    Exploitant.Activite.ELEVEUR: [
        ("Bœuf (colis ou au kg)", "Viandes", "KG", "🐄", [], Decimal("18.50")),
        ("Veau", "Viandes", "KG", "🐂", [], Decimal("21.00")),
        ("Agneau", "Viandes", "KG", "🐑", [], Decimal("19.50")),
        ("Porc", "Viandes", "KG", "🐖", [], Decimal("12.80")),
        ("Saucisse", "Viandes", "KG", "🌭", [], Decimal("13.90")),
        ("Saucisson", "Viandes", "PC", "🌭", [], Decimal("6.50")),
        ("Poulet fermier", "Volaille", "PC", "🐔", [], Decimal("14.50")),
        ("Poulet", "Volaille", "PC", "🐔", [], Decimal("12.50")),
        ("Canard", "Volaille", "PC", "🦆", [], Decimal("16.00")),
        ("Oie", "Volaille", "PC", "🦢", [], Decimal("38.00")),
        ("Œufs", "Œufs", "PC", "🥚", [], Decimal("0.45")),
        ("Œufs de poule (boîte de 6)", "Œufs", "PC", "🥚", [], Decimal("2.70")),
        ("Œufs de cane", "Œufs", "PC", "🥚", [], Decimal("3.20")),
    ],
    Exploitant.Activite.FROMAGER: [
        ("Tomme", "Fromages", "PC", "🧀", [], Decimal("8.50")),
        ("Saint-Nectaire", "Fromages", "PC", "🧀", [], Decimal("7.80")),
        ("Cantal", "Fromages", "PC", "🧀", [], Decimal("8.20")),
        ("Reblochon", "Fromages", "PC", "🧀", [], Decimal("8.90")),
        ("Chèvre", "Fromages", "PC", "🧀", [], Decimal("3.20")),
        ("Brebis", "Fromages", "PC", "🧀", [], Decimal("6.50")),
        ("Vache qui rit fermière", "Fromages", "PC", "🧀", [], Decimal("4.50")),
        ("Yaourt", "Produits laitiers", "BQ", "🥛", [], Decimal("2.80")),
        ("Faisselle", "Produits laitiers", "BQ", "🥛", [], Decimal("3.20")),
        ("Fromage blanc", "Produits laitiers", "KG", "🥛", [], Decimal("4.50")),
        ("Lait cru", "Produits laitiers", "PC", "🥛", [], Decimal("1.40")),
        ("Beurre", "Produits laitiers", "PC", "🧈", [], Decimal("3.80")),
        ("Crème fraîche", "Produits laitiers", "PC", "🥛", [], Decimal("3.20")),
    ],
    Exploitant.Activite.APICULTEUR: [
        ("Miel de fleurs", "Ruche", "PC", "🍯", [], Decimal("7.80")),
        ("Miel d'acacia", "Ruche", "PC", "🍯", [], Decimal("8.90")),
        ("Miel de châtaignier", "Ruche", "PC", "🍯", [], Decimal("8.90")),
        ("Miel de tilleul", "Ruche", "PC", "🍯", [], Decimal("8.50")),
        ("Miel de sapin", "Ruche", "PC", "🍯", [], Decimal("9.90")),
        ("Miel toutes fleurs (pot)", "Ruche", "PC", "🍯", [], Decimal("7.50")),
        ("Pollen", "Ruche", "PC", "🌼", [], Decimal("9.50")),
        ("Propolis", "Ruche", "PC", "🌿", [], Decimal("11.50")),
        ("Gelée royale", "Ruche", "PC", "👑", [], Decimal("18.00")),
        ("Cire d'abeille", "Ruche", "PC", "🕯️", [], Decimal("5.00")),
    ],
    Exploitant.Activite.MICRO_BRASSEUR: [
        ("Blonde", "Bières", "PC", "🍺", [], Decimal("3.20")),
        ("Blonde de garde", "Bières", "PC", "🍺", [], Decimal("3.60")),
        ("Ambrée", "Bières", "PC", "🍺", [], Decimal("3.50")),
        ("Rousse", "Bières", "PC", "🍺", [], Decimal("3.50")),
        ("Brune", "Bières", "PC", "🍺", [], Decimal("3.80")),
        ("Blanche", "Bières", "PC", "🍺", [], Decimal("3.30")),
        ("IPA", "Bières", "PC", "🍺", [], Decimal("3.90")),
        ("APA", "Bières", "PC", "🍺", [], Decimal("3.80")),
        ("Saison", "Bières", "PC", "🍺", [], Decimal("3.60")),
        ("Stout", "Bières", "PC", "🍺", [], Decimal("4.00")),
        ("Porter", "Bières", "PC", "🍺", [], Decimal("3.90")),
        ("Triple", "Bières", "PC", "🍺", [], Decimal("4.20")),
        ("Weizen", "Bières", "PC", "🍺", [], Decimal("3.50")),
        ("Bière sans alcool", "Bières", "PC", "🫙", [], Decimal("3.00")),
        ("Bière de Noël", "Bières", "PC", "🎄", ["hiver"], Decimal("3.90")),
        ("Fût 10 L", "Fûts", "PC", "🛢️", [], Decimal("45.00")),
        ("Fût 20 L", "Fûts", "PC", "🛢️", [], Decimal("85.00")),
        ("Fût 30 L", "Fûts", "PC", "🛢️", [], Decimal("120.00")),
    ],
    Exploitant.Activite.CONSERVERIE: [
        ("Confiture de fraise", "Confitures & gelées", "PC", "🍯", ["été"], Decimal("4.80")),
        ("Confiture d'abricot", "Confitures & gelées", "PC", "🍯", ["été"], Decimal("4.80")),
        ("Confiture de figue", "Confitures & gelées", "PC", "🍯", ["automne"], Decimal("5.20")),
        ("Confiture de myrtille", "Confitures & gelées", "PC", "🍯", ["été"], Decimal("5.50")),
        ("Gelée de coing", "Confitures & gelées", "PC", "🍯", ["automne"], Decimal("4.90")),
        ("Gelée de groseille", "Confitures & gelées", "PC", "🍯", [], Decimal("4.90")),
        ("Miel & gelée royale (pot)", "Confitures & gelées", "PC", "🍯", [], Decimal("9.50")),
        ("Tomates séchées", "Conserves de légumes", "PC", "🍅", [], Decimal("4.50")),
        ("Coulis de tomate", "Conserves de légumes", "PC", "🍅", [], Decimal("3.50")),
        ("Ratatouille en bocal", "Conserves de légumes", "PC", "🥫", [], Decimal("5.80")),
        ("Haricots verts en bocal", "Conserves de légumes", "PC", "🥫", [], Decimal("4.20")),
        ("Petits pois carotte en bocal", "Conserves de légumes", "PC", "🥫", [], Decimal("4.20")),
        ("Choucroute en bocal", "Conserves de légumes", "PC", "🥫", ["hiver"], Decimal("5.90")),
        ("Soupe de légumes (bocal)", "Soupes & coulis", "PC", "🍲", [], Decimal("4.50")),
        ("Velouté de potimarron", "Soupes & coulis", "PC", "🍲", ["automne"], Decimal("4.80")),
        ("Coulis de framboise", "Soupes & coulis", "PC", "🥫", ["été"], Decimal("4.50")),
        ("Terrine de campagne", "Terrines & pâtés", "PC", "🥫", [], Decimal("4.90")),
        ("Terrine de lapin", "Terrines & pâtés", "PC", "🥫", [], Decimal("5.50")),
        ("Pâté de foie", "Terrines & pâtés", "PC", "🥫", [], Decimal("4.80")),
        ("Rillettes d'oie", "Terrines & pâtés", "PC", "🥫", [], Decimal("5.90")),
        ("Sauce tomate basique", "Sauces & condiments", "PC", "🍅", [], Decimal("3.20")),
        ("Tapenade d'olives", "Sauces & condiments", "PC", "🫒", [], Decimal("4.50")),
        ("Câpres au vinaigre", "Sauces & condiments", "PC", "🌿", [], Decimal("3.80")),
        ("Cornichons au vinaigre", "Sauces & condiments", "PC", "🥒", [], Decimal("4.20")),
    ],
    Exploitant.Activite.FOODTRUCK: [
        ("Menu pizza (part + boisson)", "Menus", "PC", "🍕", [], Decimal("10.50")),
        ("Menu burger (burger + frites + boisson)", "Menus", "PC", "🍔", [], Decimal("12.50")),
        ("Menu sandwich (sandwich + frites + boisson)", "Menus", "PC", "🥪", [], Decimal("10.00")),
        ("Menu enfant (burger junior + frites)", "Menus", "PC", "🧒", [], Decimal("7.50")),
        ("Pizza margherita", "Pizzas", "PC", "🍕", [], Decimal("9.50")),
        ("Pizza reine", "Pizzas", "PC", "🍕", [], Decimal("11.00")),
        ("Pizza 4 fromages", "Pizzas", "PC", "🧀", [], Decimal("12.00")),
        ("Pizza au chorizo", "Pizzas", "PC", "🌶️", [], Decimal("11.50")),
        ("Pizza végétarienne", "Pizzas", "PC", "🥬", [], Decimal("10.50")),
        ("Burger classique", "Burgers", "PC", "🍔", [], Decimal("8.50")),
        ("Cheeseburger", "Burgers", "PC", "🍔", [], Decimal("9.00")),
        ("Burger au bleu", "Burgers", "PC", "🧀", [], Decimal("9.50")),
        ("Burger végétarien", "Burgers", "PC", "🥗", [], Decimal("8.50")),
        ("Double burger", "Burgers", "PC", "🍔", [], Decimal("11.50")),
        ("Sandwich mixte", "Sandwichs & Plats", "PC", "🥪", [], Decimal("5.50")),
        ("Sandwich poulet crudité", "Sandwichs & Plats", "PC", "🥪", [], Decimal("6.00")),
        ("Sandwich végétarien", "Sandwichs & Plats", "PC", "🥗", [], Decimal("5.50")),
        ("Sandwich kebab agneau", "Sandwichs & Plats", "PC", "🥙", [], Decimal("7.50")),
        ("Sandwich kebab poulet", "Sandwichs & Plats", "PC", "🍗", [], Decimal("7.00")),
        ("Plat du jour (barquette)", "Sandwichs & Plats", "PC", "🍱", [], Decimal("9.50")),
        ("Wrap du moment", "Sandwichs & Plats", "PC", "🌯", [], Decimal("6.50")),
        ("Frites maison", "Accompagnements", "PC", "🍟", [], Decimal("3.50")),
        ("Potatoes", "Accompagnements", "PC", "🍟", [], Decimal("3.50")),
        ("Salade fraîcheur", "Accompagnements", "PC", "🥗", [], Decimal("4.00")),
        ("Limonade artisanale", "Boissons", "PC", "🥤", [], Decimal("2.80")),
        ("Soda artisanal", "Boissons", "PC", "🥤", [], Decimal("2.80")),
        ("Bière locale (bouteille)", "Boissons", "PC", "🍺", [], Decimal("3.50")),
        ("Café", "Boissons", "PC", "☕", [], Decimal("1.50")),
        ("Tarte maison (part)", "Desserts", "PC", "🥧", [], Decimal("3.50")),
        ("Tiramisu", "Desserts", "PC", "🍰", [], Decimal("4.00")),
        ("Brownie", "Desserts", "PC", "🍫", [], Decimal("3.50")),
        ("Glace artisanale (pot)", "Desserts", "PC", "🍦", [], Decimal("3.50")),
    ],
    Exploitant.Activite.TRAITEUR: [
        ("Menu du jour (entrée + plat + dessert)", "Menus", "PC", "🍽️", [], Decimal("14.50")),
        ("Menu traiteur (3 services)", "Menus", "PC", "🍽️", [], Decimal("22.00")),
        ("Plateau repas", "Menus", "PC", "🍱", [], Decimal("16.50")),
        ("Cassoulet maison", "Plats cuisinés", "PC", "🥘", [], Decimal("11.50")),
        ("Blanquette de veau", "Plats cuisinés", "PC", "🥘", [], Decimal("12.00")),
        ("Potée auvergnate", "Plats cuisinés", "PC", "🍲", [], Decimal("10.50")),
        ("Gratin dauphinois", "Plats cuisinés", "PC", "🥔", [], Decimal("5.50")),
        ("Quiche lorraine (part)", "Plats cuisinés", "PC", "🥧", [], Decimal("4.50")),
        ("Tourte au canard", "Plats cuisinés", "PC", "🥧", [], Decimal("6.50")),
        ("Lasagnes de bœuf", "Plats cuisinés", "PC", "🍝", [], Decimal("9.50")),
        ("Terrine de campagne", "Terrines & pâtés", "PC", "🥫", [], Decimal("4.90")),
        ("Pâté en croûte", "Terrines & pâtés", "PC", "🥧", [], Decimal("5.50")),
        ("Rillettes maison", "Terrines & pâtés", "PC", "🥫", [], Decimal("5.50")),
        ("Salade de chèvre", "Salades composées", "PC", "🥗", [], Decimal("7.50")),
        ("Salade César", "Salades composées", "PC", "🥗", [], Decimal("8.00")),
        ("Taboulé", "Salades composées", "PC", "🥗", [], Decimal("5.50")),
        ("Céleri rémoulade", "Salades composées", "PC", "🥗", [], Decimal("4.50")),
        ("Tarte aux pommes (part)", "Desserts", "PC", "🥧", [], Decimal("3.50")),
        ("Île flottante", "Desserts", "PC", "🍮", [], Decimal("3.80")),
        ("Crème brûlée", "Desserts", "PC", "🍮", [], Decimal("4.20")),
        ("Compote maison", "Desserts", "PC", "🍎", [], Decimal("3.00")),
        ("Café (thermos 1 L)", "Boissons", "PC", "☕", [], Decimal("9.00")),
        ("Limonade artisanale", "Boissons", "PC", "🥤", [], Decimal("2.80")),
    ],
    Exploitant.Activite.RESTAURANT: [
        ("Œuf mayonnaise aux herbes", "Entrées", "PC", "🥚", ["toute l'année"], Decimal("4.50")),
        ("Terrine de foie gras maison", "Entrées", "PC", "🥫", ["automne", "hiver"], Decimal("12.50")),
        ("Salade de chèvre chaud", "Entrées", "PC", "🥗", ["printemps", "été"], Decimal("9.50")),
        ("Velouté de saison", "Entrées", "PC", "🍲", ["automne", "hiver"], Decimal("6.50")),
        ("Planche de charcuteries locales", "Entrées", "PC", "🥓", ["toute l'année"], Decimal("14.00")),
        ("Plat du jour (selon le marché)", "Plats", "PC", "🍽️", ["toute l'année"], Decimal("13.50")),
        ("Magret de canard sauce au miel", "Plats", "PC", "🍖", ["toute l'année"], Decimal("17.50")),
        ("Confit de canard pommes sarladaises", "Plats", "PC", "🍖", ["toute l'année"], Decimal("16.50")),
        ("Cassoulet maison", "Plats", "PC", "🥘", ["automne", "hiver"], Decimal("15.50")),
        ("Filet de bœuf sauce poivre", "Plats", "PC", "🥩", ["toute l'année"], Decimal("22.00")),
        ("Pavé de saumon rôti", "Plats", "PC", "🐟", ["toute l'année"], Decimal("18.00")),
        ("Dos de cabillaud à la crème", "Plats", "PC", "🐟", ["toute l'année"], Decimal("17.50")),
        ("Risotto aux cèpes", "Plats", "PC", "🍚", ["automne"], Decimal("16.00")),
        ("Tartare de bœuf au couteau", "Plats", "PC", "🥩", ["toute l'année"], Decimal("16.50")),
        ("Tarte fine de légumes de saison", "Plats", "PC", "🥧", ["printemps", "été", "automne"], Decimal("14.00")),
        ("Burger maison du chef", "Plats", "PC", "🍔", ["toute l'année"], Decimal("15.00")),
        ("Aligot maison", "Accompagnements", "PC", "🥔", ["toute l'année"], Decimal("6.50")),
        ("Gratin dauphinois", "Accompagnements", "PC", "🥔", ["toute l'année"], Decimal("5.50")),
        ("Légumes vapeur de saison", "Accompagnements", "PC", "🥦", ["toute l'année"], Decimal("4.50")),
        ("Frites maison", "Accompagnements", "PC", "🍟", ["toute l'année"], Decimal("4.50")),
        ("Tarte maison (part)", "Desserts", "PC", "🥧", ["toute l'année"], Decimal("5.50")),
        ("Tiramisu", "Desserts", "PC", "🍰", ["toute l'année"], Decimal("6.00")),
        ("Brownie", "Desserts", "PC", "🍫", ["toute l'année"], Decimal("5.50")),
        ("Glace artisanale (pot)", "Desserts", "PC", "🍦", ["toute l'année"], Decimal("4.50")),
        ("Café", "Boissons", "PC", "☕", ["toute l'année"], Decimal("2.20")),
        ("Limonade artisanale", "Boissons", "PC", "🥤", ["toute l'année"], Decimal("3.20")),
        ("Soda artisanal", "Boissons", "PC", "🥤", ["toute l'année"], Decimal("3.20")),
        ("Bière locale (bouteille)", "Boissons", "PC", "🍺", ["toute l'année"], Decimal("4.50")),
    ],
}

PRIX_MARAICHER = {
    "abricot": Decimal("4.50"), "ail (tête)": Decimal("1.20"), "artichaut": Decimal("1.80"),
    "asperge": Decimal("9.50"), "aubergine": Decimal("3.20"), "basilic": Decimal("1.80"),
    "batavia": Decimal("1.30"), "betterave rouge": Decimal("2.40"), "beurre fermier": Decimal("3.80"),
    "blette": Decimal("2.80"), "brocoli": Decimal("3.80"), "carotte": Decimal("2.20"),
    "cassis": Decimal("4.50"), "cerfeuil tubéreux": Decimal("4.20"), "cerise": Decimal("6.80"),
    "champignon de paris": Decimal("5.50"), "chicorée": Decimal("2.50"), "chou blanc": Decimal("2.50"),
    "chou de bruxelles": Decimal("4.50"), "chou kale": Decimal("3.50"), "chou romanesco": Decimal("3.20"),
    "chou rouge": Decimal("2.50"), "chou-fleur": Decimal("3.00"), "châtaigne": Decimal("6.50"),
    "ciboulette": Decimal("1.50"), "cidre (75 cl)": Decimal("4.20"), "coing": Decimal("3.20"),
    "compote": Decimal("3.80"), "concombre": Decimal("1.40"), "confiture": Decimal("4.80"),
    "coriandre": Decimal("1.50"), "courge butternut": Decimal("2.40"), "courgette": Decimal("2.50"),
    "céleri branche": Decimal("2.20"), "céleri-rave": Decimal("2.50"), "estragon": Decimal("1.50"),
    "faisselle": Decimal("3.20"), "farine de blé": Decimal("2.40"), "farine de seigle": Decimal("2.80"),
    "fenouil": Decimal("3.50"), "feuille de chêne": Decimal("1.40"), "figue": Decimal("5.50"),
    "fraise": Decimal("4.50"), "framboise": Decimal("4.80"), "fromage de chèvre": Decimal("3.20"),
    "fève": Decimal("4.50"), "girolle": Decimal("14.00"), "groseille": Decimal("4.50"),
    "haricot beurre": Decimal("6.50"), "haricot blanc": Decimal("4.20"), "haricot rouge": Decimal("4.20"),
    "haricot vert": Decimal("6.50"), "jus de pomme (1 l)": Decimal("3.50"), "laitue romaine": Decimal("1.40"),
    "lentille blonde": Decimal("4.50"), "lentille verte": Decimal("4.20"), "maïs doux": Decimal("1.50"),
    "melon": Decimal("2.80"), "menthe": Decimal("1.50"), "mesclun": Decimal("2.50"),
    "miel (500 g)": Decimal("8.50"), "myrtille": Decimal("4.80"), "mâche": Decimal("2.50"),
    "mûre": Decimal("4.50"), "navet": Decimal("2.30"), "nectarine": Decimal("3.90"),
    "oignon jaune": Decimal("2.10"), "oignon rouge": Decimal("2.60"), "pain au levain": Decimal("4.20"),
    "panais": Decimal("3.20"), "pastèque": Decimal("3.90"), "patate douce": Decimal("3.80"),
    "persil": Decimal("1.50"), "petit pois": Decimal("6.00"), "piment": Decimal("3.50"),
    "pleurote": Decimal("9.50"), "poire": Decimal("3.20"), "poireau": Decimal("2.80"),
    "pois cassé": Decimal("3.80"), "pois chiche": Decimal("4.20"), "poivron rouge": Decimal("4.20"),
    "poivron vert": Decimal("3.60"), "pomme": Decimal("2.80"), "pomme de terre (bintje)": Decimal("1.90"),
    "pomme de terre nouvelle": Decimal("2.60"), "pomme de terre vitelotte": Decimal("3.50"),
    "potimarron": Decimal("2.40"), "potiron": Decimal("2.00"), "poulet fermier": Decimal("14.50"),
    "prune": Decimal("3.60"), "pêche": Decimal("3.80"), "radis noir": Decimal("2.50"),
    "radis rose": Decimal("1.80"), "raisin de table": Decimal("4.20"), "romarin": Decimal("1.50"),
    "roquette": Decimal("2.20"), "salsifis": Decimal("3.80"), "saucisson sec": Decimal("6.50"),
    "sauge": Decimal("1.50"), "sirop de fruits": Decimal("5.20"), "sucrine": Decimal("1.60"),
    "thym": Decimal("1.50"), "tomate ananas": Decimal("4.50"), "tomate cerise": Decimal("3.20"),
    "tomate cœur de bœuf": Decimal("4.50"), "tomate ronde": Decimal("3.20"), "tomme": Decimal("8.50"),
    "yaourt fermier": Decimal("2.80"), "échalote": Decimal("4.20"), "épinard": Decimal("4.50"),
    "œufs (boîte de 6)": Decimal("2.70"),
}


EMOJIS_PAR_MOTCLE = [
    ("carotte", "🥕"), ("tomate", "🍅"), ("pomme de terre", "🥔"),
    ("patate", "🥔"), ("oignon", "🧅"), ("échalote", "🧅"),
    ("echalote", "🧅"), ("ail", "🧄"), ("courgette", "🥒"),
    ("concombre", "🥒"), ("courge", "🎃"), ("potiron", "🎃"),
    ("potimarron", "🎃"), ("citrouille", "🎃"), ("aubergine", "🍆"),
    ("poivron", "🫑"), ("piment", "🌶️"), ("salade", "🥬"),
    ("laitue", "🥬"), ("roquette", "🥬"), ("mâche", "🥬"),
    ("mache", "🥬"), ("épinard", "🥬"), ("epinard", "🥬"),
    ("choux", "🥬"), ("chou", "🥬"), ("brocoli", "🥦"),
    ("poireau", "🥬"), ("betterave", "🟣"), ("navet", "🟠"),
    ("radis", "🌶️"), ("haricot", "🫛"), ("pois", "🫛"),
    ("fève", "🫛"), ("feve", "🫛"), ("fenouil", "🌿"),
    ("céleri", "🌿"), ("celeri", "🌿"), ("asperge", "🌿"),
    ("artichaut", "🌿"), ("herbe", "🌿"), ("persil", "🌿"),
    ("basilic", "🌿"), ("ciboule", "🌿"), ("coriandre", "🌿"),
    ("thym", "🌿"), ("menthe", "🌿"), ("laurier", "🌿"),
    ("maïs", "🌽"), ("mais", "🌽"), ("champignon", "🍄"),
    ("pomme", "🍎"), ("poire", "🍐"), ("pêche", "🍑"),
    ("peche", "🍑"), ("nectarine", "🍑"), ("abricot", "🍑"),
    ("cerise", "🍒"), ("prune", "🫐"), ("fraise", "🍓"),
    ("framboise", "🍓"), ("myrtille", "🫐"), ("cassis", "🫐"),
    ("groseille", "🫐"), ("raisin", "🍇"), ("melon", "🍈"),
    ("pastèque", "🍉"), ("pasteque", "🍉"), ("kiwi", "🥝"),
    ("citron", "🍋"), ("orange", "🍊"), ("mandarine", "🍊"),
    ("clémentine", "🍊"), ("clementine", "🍊"), ("avocat", "🥑"),
    ("banane", "🍌"), ("figue", "🫒"), ("noix", "🌰"),
    ("noisette", "🌰"), ("amande", "🌰"), ("œuf", "🥚"),
    ("oeuf", "🥚"), ("lait", "🥛"), ("yaourt", "🥛"),
    ("faisselle", "🥛"), ("fromage", "🧀"), ("tomme", "🧀"),
    ("cantal", "🧀"), ("reblochon", "🧀"), ("chèvre", "🧀"),
    ("chevre", "🧀"), ("brebis", "🧀"), ("beurre", "🧈"),
    ("crème", "🥛"), ("creme", "🥛"), ("miel", "🍯"),
    ("gelée", "🍯"), ("gelee", "🍯"), ("confiture", "🍯"),
    ("bière", "🍺"), ("biere", "🍺"), ("houblon", "🍺"),
    ("fût", "🛢️"), ("fut", "🛢️"), ("jus", "🧃"), ("sirop", "🧃"),
    ("compote", "🥧"), ("tarte", "🥧"), ("pain", "🍞"),
    ("farine", "🌾"), ("lentille", "🫘"), ("pois chiche", "🫘"),
    ("haricot sec", "🫘"), ("huile", "🫒"), ("olive", "🫒"),
    ("bœuf", "🐄"), ("boeuf", "🐄"), ("veau", "🐂"),
    ("agneau", "🐑"), ("mouton", "🐑"), ("porc", "🐖"),
    ("saucisse", "🌭"), ("saucisson", "🌭"), ("jambon", "🥓"),
    ("poulet", "🐔"), ("canard", "🦆"), ("oie", "🦢"),
    ("dinde", "🦃"), ("lapin", "🐇"), ("escargot", "🐌"),
    ("truite", "🐟"), ("saumon", "🐟"), ("poisson", "🐟"),
    ("blette", "🥬"), ("cardon", "🌿"), ("châtaigne", "🌰"),
    ("chataigne", "🌰"), ("coing", "🍏"), ("figue", "🫒"),
    ("mûre", "🫐"), ("mure", "🫐"), ("panais", "🥕"),
    ("salsifis", "🥕"), ("cerfeuil", "🌿"), ("topinambour", "🥔"),
    ("mesclun", "🥬"), ("sucrine", "🥬"), ("chicorée", "🥬"),
    ("chicoree", "🥬"), ("estragon", "🌿"), ("romarin", "🌿"),
    ("sauge", "🌿"), ("girolle", "🍄"), ("pleurote", "🍄"),
    ("cèpe", "🍄"), ("cepe", "🍄"), ("cidre", "🍹"),
    ("perry", "🍹"), ("poiré", "🍹"),
    ("terrine", "🥫"), ("pâté", "🥫"), ("pate", "🥫"),
    ("rillettes", "🥫"), ("bocal", "🥫"), ("conserve", "🥫"),
    ("vinaigre", "🫙"), ("tapenade", "🫒"), ("câpre", "🌿"),
    ("soupe", "🍲"), ("velouté", "🍲"), ("veloute", "🍲"),
    ("ratatouille", "🥫"), ("sauce", "🍅"), ("coulis", "🥫"),
]


def emoji_pour_nom(nom):
    """Emoji deviné par mot-clé du nom du produit — comparaison SANS
    accent ni casse (« Échalote » → échalote → 🧅). Défaut : symbole
    de l'activité (🥬 maraîcher)."""
    texte = unicodedata.normalize("NFKD", nom.lower())
    texte = "".join(c for c in texte if not unicodedata.combining(c))
    for motcle, emoji in EMOJIS_PAR_MOTCLE:
        cle = unicodedata.normalize("NFKD", motcle)
        cle = "".join(c for c in cle if not unicodedata.combining(c))
        if cle in texte:
            return emoji
    return ""


class Command(BaseCommand):
    help = ("Charge les catalogues de produits types par activité "
            "(idempotent : lancez-le après chaque mise à jour).")

    def handle(self, *args, **options):
        # 1. Le catalogue existant est explicitement classé maraîcher
        #    et enrichi de prix indicatifs réalistes par défaut.
        ProduitStandard.objects.filter(activite="").update(
            activite=Exploitant.Activite.MARAICHER)
        maraichers = ProduitStandard.objects.filter(
            activite=Exploitant.Activite.MARAICHER)
        prix_maraichers_ajoutes = 0
        for std in maraichers:
            prix = PRIX_MARAICHER.get(std.nom.lower())
            if not prix:
                if std.unite_vente == ProduitStandard.Unite.KG:
                    prix = Decimal("2.80")
                elif std.unite_vente == ProduitStandard.Unite.BOTTE:
                    prix = Decimal("1.80")
                elif std.unite_vente == ProduitStandard.Unite.BARQUETTE:
                    prix = Decimal("3.50")
                else:
                    prix = Decimal("1.50")
            if std.prix_indicatif != prix:
                std.prix_indicatif = prix
                std.save(update_fields=["prix_indicatif"])
                prix_maraichers_ajoutes += 1
        self.stdout.write(f"Catalogue maraîcher : {maraichers.count()} produit(s) "
                          f"({prix_maraichers_ajoutes} prix indicatif(s) mis à jour).")

        # 2. Les catalogues des autres activités avec prix indicatifs réalistes.
        for activite, produits in CATALOGUES.items():
            crees = 0
            prix_maj = 0
            for item in produits:
                if len(item) == 6:
                    nom, categorie, unite, emoji, saisons, prix_indicatif = item
                else:
                    nom, categorie, unite, emoji, saisons = item
                    prix_indicatif = None
                std, cree = ProduitStandard.objects.get_or_create(
                    activite=activite, nom=nom,
                    defaults={"categorie": categorie, "unite_vente": unite,
                              "emoji": emoji, "saisons": saisons,
                              "prix_indicatif": prix_indicatif})
                if cree:
                    crees += 1
                elif prix_indicatif is not None and std.prix_indicatif != prix_indicatif:
                    std.prix_indicatif = prix_indicatif
                    std.save(update_fields=["prix_indicatif"])
                    prix_maj += 1
            libelle = Exploitant.Activite(activite).label
            total = ProduitStandard.objects.filter(activite=activite).count()
            self.stdout.write(
                f"{libelle} : {total} produit(s) "
                f"({crees} nouveau(x), {prix_maj} prix indicatif(s) mis à jour).")

        # 3. Aucun produit type sans emoji : on devine le symbole par
        #    mot-clé du nom, avec le symbole de l'activité en dernier
        #    recours — chaque produit a ainsi son emoji (vignettes,
        #    commandes, paniers, récoltes).
        sans_emoji = ProduitStandard.objects.filter(emoji="")
        remplaces = 0
        for std in sans_emoji:
            emoji = emoji_pour_nom(std.nom)
            if not emoji:
                emoji = Exploitant.ACTIVITE_EMOJIS.get(
                    std.activite, "🌱")
            std.emoji = emoji
            std.save(update_fields=["emoji"])
            remplaces += 1
        self.stdout.write(f"Emojis complétés : {remplaces} produit(s).")

        # 4. Emojis des produits des FERMES (Produit) : hérités du
        #    produit type d'origine, sinon devinés par mot-clé, sinon
        #    symbole de l'activité de la ferme — chaque produit finit
        #    avec son symbole dans toutes les listes (commandes,
        #    paniers, vitrine, commander).
        par_activite = {
            Exploitant.Activite.MARAICHER: "🥬",
            Exploitant.Activite.ARBORICULTEUR: "🍎",
            Exploitant.Activite.ELEVEUR: "🐄",
            Exploitant.Activite.FROMAGER: "🧀",
            Exploitant.Activite.APICULTEUR: "🍯",
            Exploitant.Activite.MICRO_BRASSEUR: "🍺",
            Exploitant.Activite.CONSERVERIE: "🥫",
            Exploitant.Activite.FOODTRUCK: "🚚",
            Exploitant.Activite.TRAITEUR: "🥗",
            Exploitant.Activite.RESTAURANT: "🍽️",
            Exploitant.Activite.AUTRE: "🌾",
        }
        majs = 0
        for produit in (Produit.objects.filter(emoji="")
                        .select_related("origine_standard", "exploitant")):
            emoji = ""
            if produit.origine_standard_id and produit.origine_standard:
                emoji = produit.origine_standard.emoji or ""
            emoji = (emoji or emoji_pour_nom(produit.nom)
                     or par_activite.get(produit.exploitant.activite, "🌾"))
            produit.emoji = emoji
            produit.save(update_fields=["emoji"])
            majs += 1
        self.stdout.write(f"Emojis produits des fermes : {majs} complété(s).")

        self.stdout.write(self.style.SUCCESS(
            "Catalogues par activité chargés."))
