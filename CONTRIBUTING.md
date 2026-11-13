# 🤝 Contribuer à MonPetitProducteurLocal

Merci de vouloir contribuer ! MonPetitProducteurLocal est un projet porté pour et par les **producteurs, artisans et restaurateurs locaux**, ainsi que tous les acteurs qui renforcent les circuits courts de proximité.

Toutes les contributions sont les bienvenues : code, tests, documentation, design, retours terrain des producteurs et des consommateurs.

---

## ⚖️ Licence & Accord de Contribution (CLA)

Le projet est distribué sous un **modèle de double licence** :
1. Une **licence libre GNU AGPL-3.0** (Open Source pour le bien commun et l'auto-hébergement communautaire) ;
2. Une **licence commerciale** pour les services managés (SaaS éthique), les déploiements garantis avec support et les usages propriétaires.

### Accord de contribution :
En soumettant une contribution (Pull Request, patch, code, documentation ou design) au projet MonPetitProducteurLocal, vous acceptez les termes suivants :

1. **Garantie d'originalité** : Vous certifiez que vous êtes l'auteur légitime du code ou du contenu soumis, ou que vous disposez des droits nécessaires pour le soumettre.
2. **Licence accordée** : Vous accordez à l'éditeur du projet (**Cartotrac**) une licence mondiale, non exclusive, perpétuelle, irrévocable, transférable et libre de redevances d'utiliser, reproduire, modifier, distribuer et sous-licencier vos contributions sous la licence GNU AGPL-3.0, ainsi que sous toute licence commerciale, propriétaire ou d'hébergement SaaS proposée par le projet.
3. **Maintien de vos droits** : Vous conservez l'entière paternité et vos propres droits d'auteur sur votre travail original.

Cet accord est indispensable pour assurer la pérennité du projet, permettre son financement via un modèle SaaS éthique et préserver la gouvernance du logiciel face au risque de blocage juridique.

---

## 🚀 Comment contribuer

1. **Forkez** le dépôt officiel puis créez votre branche de travail :
   ```bash
   git switch -c feat/ma-fonctionnalite
   ```
2. **Développez** vos modifications en respectant les conventions de branches :
   * `feat/…` : nouvelle fonctionnalité
   * `fix/…` : correction de bogue
   * `doc/…` : documentation
   * `ui/…` : design, accessibilité et styles
3. **Vérifiez** que le projet est propre et valide :
   ```bash
   python manage.py check
   ```
4. **Ouvrez une Pull Request** claire décrivant :
   * Le problème ou le besoin terrain résolu ;
   * Le détail des modifications apportées ;
   * La démarche concrète pour tester la modification.

---

## 💡 Principes de conception du projet

* **Sobriété technique** : Stack Python/Django simple, dépendances minimales, pas de framework front lourd, hébergeable facilement sur AlwaysData ou serveur dédié.
* **Indépendance des pros locaux** : Chaque professionnel reste maître de ses données, de ses prix, de ses récoltes et de sa relation client. Le portail est un outil, pas un intermédiaire prédateur.
* **Réplicabilité & Bien Commun** : Tout collectif ou association doit pouvoir reproduire et déployer sa propre instance locale.
* **Accessibilité & Mobilité** : Interfaces soignées, fluides sur smartphone, respectueuses du mode clair et du mode sombre.

---

## 🐛 Signaler un problème ou suggérer une idée

Ouvrez une *issue* sur GitHub en précisant :
* Le contexte (rôle : client / producteur / administrateur, type d'appareil, navigateur) ;
* Les étapes pas à pas pour reproduire l'anomalie ;
* Le résultat obtenu vs le résultat attendu.

---

## 📬 Contact & Gouvernance

Pour toute question relative aux orientations du projet ou à l'offre SaaS managée :
* **Site** : [cartotrac.fr](https://cartotrac.fr)
* **Discussions GitHub** : [Issues MonPetitProducteurLocal](https://github.com/cartotrac/MonPetitProducteurLocal/issues)
