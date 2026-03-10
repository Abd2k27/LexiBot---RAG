# Projet SENTINELLE v3
**Système Éducatif Numérique de Triage et d'Intervention Locale pour les Élèves**

---

## 1. Vision

Déployer un filet de sécurité numérique **agentique et souverain** capable de :
- **Écouter** les élèves en temps réel via un chatbot empathique, contrôlé par un double système d'agents IA
- **Veiller** silencieusement sur leurs écrits via l'analyse différée et contextuelle de leurs journaux
- **Alerter** les professionnels avec un langage clinique structuré (modèle RUD)

Le tout hébergé **localement**, garantissant la souveraineté des données, la maîtrise des coûts et la conformité réglementaire.

---

## 2. Problématiques et Solutions Apportées

| Problème | Impact | Solution SENTINELLE v3 |
|---|---|---|
| Score linéaire 0-100 non borné | Explosion des scores, faux positifs | **Sigmoïde bornée (0-10)** — saturation mathématique |
| Filtre regex rigide rate les signaux subtils | Faux négatifs dangereux | **Agents IA locaux** — compréhension contextuelle |
| Dépendance API LLM = coût explosif | Budget non viable à l'échelle | **Serveur local (vLLM/Ollama)** — coût fixe |
| LLM peut halluciner des conseils dangereux | Risque clinique | **Agent Guardian** — validation systématique |
| Variables F et H sans stockage | Impossible de détecter les tendances | **Profil élève agrégé** avec historique 30 jours |
| Batch nocturne sans filet temps réel | Angle mort temporel jusqu'à 16h | **Filtre immédiat** sur mots-clés critiques + batch 2×/jour |
| Aucun feedback des professionnels | Pas d'amélioration continue | **Boucle de feedback** humain-dans-la-boucle |
| Données sensibles sur serveurs tiers | Risque RGPD/HDS | **Hébergement local** — rien ne sort de l'infra |

---

## 3. Architecture Globale : Le Double Pipeline Agentique

```
                    ┌───────────────────────────────────────────────────┐
                    │              SENTINELLE v3 — Serveur Local        │
                    │              (vLLM / Ollama + GPU)                │
                    │                                                   │
   Élève écrit      │   ┌──────────────────┐  ┌──────────────────┐     │
   dans son    ────────►│  PIPELINE JOURNAL │  │ PIPELINE CHATBOT │◄───────── Élève
   journal          │   │  (Sentinelle      │  │ (Écoute Active   │     │     envoie
                    │   │   Silencieuse)    │  │  Agentique)      │     │     un message
                    │   └────────┬─────────┘  └────────┬─────────┘     │
                    │            │                      │               │
                    │            ▼                      ▼               │
                    │   ┌──────────────────────────────────────┐       │
                    │   │     PROFIL ÉLÈVE AGRÉGÉ              │       │
                    │   │  Corrélation Journal ↔ Chat          │       │
                    │   │  Historique (H), Fréquence (F)       │       │
                    │   └──────────────┬───────────────────────┘       │
                    │                  │                                │
                    │                  ▼                                │
                    │   ┌──────────────────────────────────────┐       │
                    │   │     ALERTING & RUD                    │       │
                    │   │  Notifications, Rapports cliniques    │       │
                    │   └──────────────────────────────────────┘       │
                    └───────────────────────────────────────────────────┘
```

---

## 4. Pipeline Chatbot : Le "Double Check" Agentique

L'innovation clé est la **chaîne de confiance à deux agents**. Puisque tout tourne en local, le double appel ne coûte rien de plus par requête — on peut donc se permettre cette sécurité.

### 4.1 Agent 1 : L'Assistant Empathique (RAG)

| Caractéristique | Détail |
|---|---|
| **Rôle** | Écouter et répondre avec empathie |
| **Modèle** | Llama 3 (8B) ou Mistral 7B via vLLM/Ollama |
| **Fonctionnement** | Reçoit le message, consulte la base de connaissances (fiches validées par des psychologues) via RAG, génère une réponse |
| **Contrainte système** | Consigne stricte : ne jamais diagnostiquer, ne jamais prescrire, orienter uniquement |
| **Base RAG** | Vectorstore local (ChromaDB/Qdrant) indexant les fiches pratiques validées |

### 4.2 Agent 2 : Le Contrôleur de Sécurité ("The Guardian")

| Caractéristique | Détail |
|---|---|
| **Rôle** | Valider la réponse d'Agent 1 ET qualifier le risque |
| **Modèle** | Modèle léger (Phi-3 ou Mistral 7B) avec un prompt différent — "cerveau" séparé |
| **Input** | Le couple [Message de l'élève + Réponse proposée par Agent 1] |
| **Output** | Verdict (Vert / Orange / Rouge) + Score de criticité |

**Logique de décision du Guardian :**

| Verdict | Condition | Action |
|---|---|---|
| 🟢 **Vert** | La réponse est sûre, cohérente, pas de signal critique | La réponse d'Agent 1 est envoyée telle quelle |
| 🟠 **Orange** | Le risque monte OU la réponse est floue/inappropriée | Le Guardian **réécrit** la réponse : empathie directe + orientation explicite vers CPE/infirmerie |
| 🔴 **Rouge** | Risque critique détecté (triplet de criticité, mots-clés majeurs) | **Blocage total** → Message de secours fixe + numéros d'urgence + alerte humaine immédiate |

### 4.3 Flux complet du Chatbot

```
Message de l'élève
    │
    ▼
[Pré-filtre rapide — mots-clés critiques]
    │
    ├── Mot-clé critique détecté (suicide, plan explicite)
    │       │
    │       ▼
    │   [COURT-CIRCUIT → Réponse déterministe fixe + Alerte]
    │   (Agent 1 et Agent 2 ne sont même pas appelés)
    │
    └── Pas de court-circuit
            │
            ▼
        [Agent 1 : Assistant RAG]
        Génère une réponse empathique basée sur la base de connaissances
            │
            ▼
        [Agent 2 : Guardian]
        Analyse le couple [Message élève + Réponse Agent 1]
            │
            ├── 🟢 Vert → Réponse envoyée
            ├── 🟠 Orange → Réponse reformulée par Guardian + orientation
            └── 🔴 Rouge → Réponse bloquée → Message fixe + Alerte
```

> **Pourquoi le pré-filtre reste nécessaire ?** Parce que pour les cas évidents ("je vais me tuer ce soir"), invoquer deux agents IA est inutile et ajoute de la latence. Le pré-filtre (rapide, déterministe, infaillible sur les cas explicites) court-circuite directement vers la réponse de sécurité.

> **Pourquoi deux agents et pas un seul bien prompté ?** Parce qu'un agent ne peut pas simultanément être dans l'empathie ET dans l'évaluation critique. Le biais d'empathie pousse l'Agent 1 à minimiser le risque pour "rassurer". Le Guardian, lui, n'a aucune mission d'empathie — il est une sentinelle froide et méthodique. Cette séparation des "cerveaux" est la clé de la résilience anti-hallucination.

---

## 5. Pipeline Journal : "L'Analyseur de Trajectoire"

Le journal n'est pas une urgence conversationnelle — c'est un **signal de fond**. L'approche agentique transforme du texte brut émotionnel en données structurées exploitables par la formule sigmoïde.

### 5.1 Étape 1 : Filtre Immédiat (temps réel)

À chaque écriture dans le journal, un **pré-filtre local** (mots-clés, regex) tourne en temps réel :
- **Aucun signal critique** → Le journal est stocké pour le batch
- **Signal critique détecté** → Même court-circuit que le chatbot : alerte immédiate

> **Cela résout l'angle mort temporel** : si un élève écrit à 8h *"ce soir je passerai à l'acte"*, le filtre le détecte immédiatement sans attendre le batch.

### 5.2 Étape 2 : Analyse Batch (2× par jour : midi + minuit)

Deux agents travaillent en séquence :

#### Agent Résumeur

| Caractéristique | Détail |
|---|---|
| **Rôle** | Lire les entrées du jour et en extraire une synthèse structurée |
| **Modèle** | Llama 3 (8B) via vLLM |
| **Input** | Texte brut du journal de la journée |
| **Output structuré** | Humeur (1-10), événements clés, signaux détectés, mots-clés de risque |

Exemple de sortie de l'Agent Résumeur :
```json
{
  "date": "2026-03-09",
  "mood_score": 3,
  "events": ["conflit avec camarade", "exclusion à la cantine"],
  "signals": ["isolement", "tristesse récurrente"],
  "criticality_triplet": {
    "intention": false,
    "moyen": false,
    "temporalite": false
  },
  "raw_sentiment": "négatif",
  "key_quote": "Personne ne me parle, je suis invisible."
}
```

#### Agent Scoreur

| Caractéristique | Détail |
|---|---|
| **Rôle** | Calculer le score sigmoïde $S_r$ à partir du résumé du jour + historique 30 jours |
| **Input** | Résumé du jour + 30 derniers résumés |
| **Output** | Variables $I, F, C, H$ alimentant la sigmoïde → $S_r$ final |

> **Pourquoi cette approche est plus sûre ?** Parce que l'IA ne juge pas le risque sur une phrase isolée sortie de son contexte, mais sur une **synthèse clinique** de la journée, comparée à la trajectoire des 30 derniers jours. Un élève qui écrit "je suis triste" une fois n'est pas traité comme celui qui l'écrit tous les jours depuis 3 semaines.

---

## 6. Scoring Résilient : La Sigmoïde Bornée

### 6.1 Formule

Soit $Z$ la somme pondérée des facteurs :

$$Z = (w_i \cdot I) + (w_f \cdot F) + (w_c \cdot C) + (w_h \cdot H) - \text{biais}$$

Le score résilient $S_r$ (borné de 0 à 10) :

$$S_r = \frac{10}{1 + e^{-Z}}$$

### 6.2 Variables et leur alimentation par les agents

| Variable | Signification | Source Chatbot | Source Journal |
|---|---|---|---|
| **$I$** (Intensité) | Gravité lexicale | Évaluation directe par le Guardian | Extraction par l'Agent Résumeur (mood_score normalisé) |
| **$F$** (Fréquence) | Récurrence sur 7 jours | Comptage des signaux chat récents dans le profil | Comptage des résumés à risque dans l'historique batch |
| **$C$** (Criticité) | Présence d'un plan concret | Triplet de criticité (Guardian) | Triplet de criticité (Agent Résumeur) |
| **$H$** (Historique) | Vulnérabilité connue | Profil élève (renseigné par CPE/psy) | Profil élève (même source) |

### 6.3 Calcul de la Fréquence ($F$)

$$F = \sum_{j=1}^{7} \alpha^{j-1} \cdot \mathbb{1}[\text{risque}_j > 0]$$

Avec $\alpha = 0.8$ (pondération de récence : les signaux récents comptent plus).

| Jour | j=1 (aujourd'hui) | j=2 (hier) | j=3 | j=4 | j=5 | j=6 | j=7 |
|---|---|---|---|---|---|---|---|
| Poids | 1.0 | 0.8 | 0.64 | 0.51 | 0.41 | 0.33 | 0.26 |

### 6.4 Triplet de Criticité ($C$)

Un **plan concret** de passage à l'acte se caractérise par la présence simultanée de trois éléments :

| Élément | Exemples | Catégorie |
|---|---|---|
| **Intention** | "je vais", "j'ai décidé", "ce sera bientôt fini" | Verbes d'action au futur / décision |
| **Moyen** | "médicaments", "corde", "couteau", "sauter", "pont" | Objets ou méthodes connus |
| **Temporalité** | "ce soir", "demain", "après les cours", "cette nuit" | Marqueurs de temps |

| Co-occurrence | Valeur de $C$ | Action |
|---|---|---|
| 0 ou 1 élément | $C = 0$ | Pas de criticité |
| 2 éléments | $C = 0.5$ | Vigilance accrue |
| 3 éléments (Intention + Moyen + Temporalité) | $C = 1.0$ | **Alerte critique immédiate** |

> **Avantage de l'approche agentique :** Dans le pipeline chatbot, c'est le **Guardian** qui évalue le triplet — pas un regex. Il peut donc détecter des formulations indirectes comme *"bientôt tout sera fini, j'ai trouvé ce qu'il faut dans la salle de bain"* (intention implicite + moyen implicite + temporalité implicite) qu'un regex raterait.

### 6.5 Poids recommandés

| Paramètre | Valeur | Justification |
|---|---|---|
| $w_i$ | 1.0 | Référence |
| $w_f$ | 0.8 | La fréquence seule ne suffit pas à déclencher un score critique |
| $w_c$ | 2.0 | **Poids le plus fort** — un plan concret est le prédicteur n°1 |
| $w_h$ | 0.6 | L'historique module mais ne détermine pas |
| biais | 2.5 | Centre la sigmoïde : un texte neutre → $S_r \approx 0.7$ |

### 6.6 Comportement de la sigmoïde

```
Sr
10 ┤                                    ●●●●●●●●●●●●●●●  ← Saturation
   │                                ●●●
 8 ┤                             ●●●
   │                           ●●
 7 ┤  - - - - - - - - - - - -●- - - - - - Seuil d'alerte rouge
   │                        ●
 5 ┤                      ●
   │                    ●
 3 ┤  - - - - - - - -●- - - - - - - - - - Seuil de vigilance
   │              ●●●
 1 ┤          ●●●
   │  ●●●●●●●                           ← Saturation basse
 0 ┼────────────────────────────────────► Z
  -5  -4  -3  -2  -1   0   1   2   3   4   5
```

**Propriété clé :** Ajouter des mots-clés à un texte déjà critique ne fait pas exploser le score. Et un texte faiblement à risque ne peut jamais dépasser ~3 par accumulation seule.

---

## 7. Couche de Réponse : Garde-fous par Conception

### 7.1 Les 3 modes

| Score $S_r$ | Mode | Comportement | Qui génère ? |
|---|---|---|---|
| **0 – 3** | **Génératif** | Réponse empathique personnalisée, suggestions bien-être | Agent 1 (RAG), validé par Guardian |
| **3 – 7** | **Semi-scripté** | Empathie + orientation explicite vers CPE/infirmerie | Guardian reformule la réponse d'Agent 1 |
| **7 – 10** | **Déterministe** | **Aucune IA.** Message fixe + numéros d'urgence + alerte | Réponse hardcodée |

### 7.2 Réponse déterministe de sécurité (Mode Critique, $S_r > 7$)

```
🚨 Ce que tu ressens est important et mérite une aide immédiate.

Tu n'es pas seul·e. Voici des personnes formées pour t'écouter :

📞 3114 — Numéro national de prévention du suicide (24h/24)
📞 119 — Enfance en danger (24h/24)
📱 Fil Santé Jeunes : 0 800 235 236 (gratuit, anonyme)

💬 Parle aussi à un adulte de confiance près de toi :
ton professeur principal, l'infirmier·e scolaire, ou le·la CPE.

[L'équipe éducative de ton établissement a été prévenue.]
```

> Aucune génération IA. Aucune possibilité d'hallucination. Message figé et validé cliniquement.

---

## 8. Alignement Clinique : Modèle RUD

Le système traduit ses scores en langage clinique via la grille **Risque-Urgence-Dangerosité** :

| Dimension RUD | Variable SENTINELLE | Évaluation |
|---|---|---|
| **Risque** (vulnérabilité) | $H$ (Historique) | Antécédents, contexte familial, suivis en cours |
| **Urgence** (imminence) | $F$ (Fréquence) | Accélération des signaux sur 7 jours |
| **Dangerosité** (létalité) | $I + C$ (Intensité + Criticité) | Gravité du propos + présence d'un plan concret |

**Exemple de rapport pour le psychologue scolaire :**

```json
{
  "resilient_score": 8.2,
  "rud": {
    "risque": "ÉLEVÉ — Antécédent de suivi psy (H=1.0)",
    "urgence": "MODÉRÉE — 3 signaux en 7 jours, tendance croissante",
    "dangerosite": "ÉLEVÉE — Mention d'un moyen et d'un moment précis"
  },
  "response_mode": "deterministic",
  "recommended_action": "Entretien immédiat avec l'élève",
  "journal_trajectory": "Dégradation progressive sur 15 jours (Sr: 2.1 → 4.5 → 8.2)"
}
```

---

## 9. Profil Élève Agrégé : Le Lien Chat ↔ Journal

### 9.1 Structure du profil

```json
{
  "student_hash": "a7f3b2...",
  "vulnerability_index": 0.5,
  "recent_signals": [
    {"date": "2026-03-07", "source": "journal", "sr": 4.2, "labels": ["isolement"]},
    {"date": "2026-03-07", "source": "chat", "sr": 3.1, "labels": ["anxiete"]},
    {"date": "2026-03-08", "source": "chat", "sr": 6.8, "labels": ["idees_noires"]}
  ],
  "daily_summaries": [
    {"date": "2026-03-08", "mood": 3, "events": ["conflit"], "signals": ["isolement"]}
  ],
  "trend": "degrading",
  "last_alert": null,
  "feedback_history": []
}
```

### 9.2 Corrélation croisée

Si un signal est détecté dans le **journal** ET un signal lié est détecté dans le **chat** dans un intervalle de 48h, le score $F$ reçoit un **bonus de corrélation** de +0.3.

> Exemple : L'élève écrit dans son journal qu'il est harcelé (Signal A) puis demande au chatbot *"comment disparaître sans douleur"* (Signal B). Le système sait que c'est le même élève et amplifie le score.

### 9.3 Feedback humain

Les professionnels peuvent :
- **Valider** une alerte → renforce la sensibilité du profil
- **Invalider** un faux positif → réduit progressivement la sensibilité
- **Mettre à jour $H$** → modifier l'historique de vulnérabilité manuellement

---

## 10. Infrastructure : Le Serveur Local

### 10.1 Pourquoi local ?

| Critère | API Cloud (OpenAI/Anthropic) | Serveur Local (vLLM/Ollama) |
|---|---|---|
| **Coût par requête** | ~0.01–0.05 € | ~0 € (coût fixe matériel) |
| **Coût à l'échelle** | Explose avec le volume | Constant |
| **Confidentialité** | Données transitent chez un tiers | Données ne sortent jamais de l'infra |
| **Latence** | Variable (réseau) | Faible et prévisible |
| **Conformité HDS** | Complexe (sous-traitance) | Simplifiée (souveraineté totale) |
| **Double appel agent** | Coût × 2 | Le même GPU sert les deux agents |

### 10.2 Stack technique recommandée

| Composant | Technologie | Rôle |
|---|---|---|
| **Hébergement LLM** | vLLM ou Ollama | Servir les modèles Llama/Mistral localement |
| **Agent RAG (Agent 1)** | Llama 3 (8B ou 70B) + ChromaDB | Réponse empathique basée sur les fiches validées |
| **Agent Guardian (Agent 2)** | Phi-3 ou Mistral 7B | Validation ultra-rapide et détection de criticité |
| **Agent Résumeur** | Llama 3 (8B) | Synthèse structurée des journaux |
| **Agent Scoreur** | Script Python + Sigmoïde | Calcul de $S_r$ (pas besoin de LLM, c'est du calcul) |
| **Base vectorielle** | ChromaDB ou Qdrant | Stockage des fiches RAG |
| **Profil élève** | PostgreSQL ou Redis | Historique, scores, résumés |
| **API** | FastAPI (existant) | Exposition des endpoints |
| **GPU** | NVIDIA RTX 4090 ou A100 | Inférence locale |

### 10.3 Estimation budgétaire infrastructure

| Composant | Coût estimé (mensuel) |
|---|---|
| Serveur GPU dédié (RTX 4090) | ~200-400 €/mois (OVH, Scaleway) |
| Stockage base de données | ~20 €/mois |
| Maintenance/monitoring | ~50 €/mois |
| **Total** | **~270-470 €/mois (fixe)** |

> Contre ~2 000-5 000 €/mois sur APIs cloud pour le même volume avec le double appel agentique. Et le coût local **ne varie pas** que vous ayez 100 ou 50 000 requêtes/jour.

---

## 11. Classification en 5 Classes SENTINELLE

Les catégories v1 sont consolidées en 5 classes cliniquement distinctes :

| Classe SENTINELLE | Catégories v1 fusionnées | Logique |
|---|---|---|
| **Harcèlement** | C (insultes), D (exclusion en contexte de harcèlement), E (cyber), G (rumeurs) | Agression relationnelle répétée |
| **Violence** | A (physique), B (menaces), F (racket) | Agression physique ou matérielle |
| **Idées noires** | I (idées noires), H (détresse psychologique) | Souffrance psychique et risque suicidaire |
| **Isolement** | D (exclusion sans harcèlement), + signaux de retrait/mutisme | Repli social sans agression externe |
| **Radicalisation** | Nouvelle catégorie | Discours extrémiste, rupture identitaire |

> Les catégories A-I sont conservées en interne pour la granularité analytique. Les 5 classes servent à la communication avec les professionnels.

---

## 12. Sécurité et Confidentialité (Privacy-by-Design)

| Principe | Implémentation |
|---|---|
| **Silos de données** | Le texte brut est analysé en mémoire et **jamais persisté**. Seuls le score $S_r$, les labels et les résumés structurés sont stockés. |
| **Anonymisation par défaut** | Les logs ne contiennent qu'un hash. L'identité nominative n'est transmise que si $S_r > 7$. |
| **Souveraineté** | Hébergement local — aucune donnée ne transite chez un tiers (OpenAI, Google, etc.) |
| **Droit à l'oubli** | Données de profil purgées après 12 mois d'inactivité. |
| **Fine-tuning local** | Les modèles peuvent être spécialisés sur des données de psychologie scolaire sans exposer les données à l'extérieur. |

---

## 13. Synthèse des Deux Pipelines

| | Chatbot (Écoute Active) | Journal (Sentinelle Silencieuse) |
|---|---|---|
| **Fréquence** | Temps réel | Batch 2×/jour + filtre immédiat |
| **Agents IA** | Agent RAG + Agent Guardian | Agent Résumeur + Agent Scoreur |
| **Coût** | Fixe (serveur local) | Fixe (même serveur) |
| **Objectif** | Soutien immédiat, empathie | Détection de tendances, alerte précoce |
| **Risque IA** | Hallucination de conseils | Faux positifs / faux négatifs |
| **Résilience** | Double Check agentique + court-circuit déterministe | Résumé contextuel + scoring sigmoïde sur 30 jours |
| **Variables scoring** | $I$ + $C$ (temps réel) + $H$ (profil) | $I + F + C + H$ (analyse complète) |

---

## 14. Priorités d'Implémentation

| Phase | Contenu | Prérequis | Durée estimée |
|---|---|---|---|
| **Phase 1** | Scoring sigmoïde + Garde-fous déterministes + Pré-filtre | Code existant | 1-2 semaines |
| **Phase 2** | Classification 5 classes + Alignement RUD + Triplet de Criticité | Phase 1 | 1 semaine |
| **Phase 3** | Serveur local (vLLM/Ollama) + Agent RAG + Agent Guardian | GPU dédié | 2-3 semaines |
| **Phase 4** | Store profil élève + Variables F et H + Feedback humain | PostgreSQL/Redis | 2-3 semaines |
| **Phase 5** | Agent Résumeur + Agent Scoreur + Batch processing | Phase 3 + 4 | 1-2 semaines |
| **Phase 6** | Corrélation croisée Chat ↔ Journal + Fine-tuning modèles | Phase 5 | 2-3 semaines |
| **Phase 7** | Audit sécurité + Validation clinique + Conformité HDS | Partenariat psy/HDS | Variable |

---

## 15. Limites Assumées

1. **Calibration des poids** : les poids $w_i, w_f, w_c, w_h$ sont des estimations initiales. La calibration rigoureuse nécessite un dataset annoté par des cliniciens, à constituer au fil du déploiement.

2. **Qualité du RAG** : l'Agent RAG n'est aussi bon que sa base de connaissances. La rédaction et la validation des fiches par des psychologues scolaires est un chantier éditorial à part entière.

3. **Radicalisation** : la détection par mots-clés est limitée pour ce sujet. Un partenariat avec des experts spécialisés est recommandé.

4. **Signaux ultra-subtils** : des expressions comme *"bientôt tout ira mieux pour tout le monde"* (euphémisme suicidaire) restent un défi même pour les agents IA. Le fine-tuning sur des cas cliniques réels améliorera progressivement cette détection.

5. **GPU requis** : le serveur local nécessite un investissement matériel initial. Alternative : commencer avec un SLM via API cloud (Groq/Together AI) en Phase 3, puis migrer localement.

6. **Responsabilité juridique** : SENTINELLE est un outil d'**aide au triage**, pas un dispositif médical. Il ne remplace jamais l'évaluation humaine. Ce cadrage juridique doit être formalisé avant le déploiement.
