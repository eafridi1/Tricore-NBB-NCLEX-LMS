import asyncio
from database import SessionLocal
from models import Question, Difficulty, QStatus, User
from sqlalchemy import select

QUESTIONS = [
    # ── Category 1: Cardiovascular ────────────────────────────────────────────
    {
        "category_id": 1,
        "difficulty": Difficulty.easy,
        "nclex_domain": "Physiological Integrity",
        "stem": (
            "A nurse is assessing a client's cardiac monitor and notes a regular rhythm "
            "with a rate of 78 bpm, a P wave before every QRS, and a PR interval of 0.18 "
            "seconds. Which interpretation is correct?"
        ),
        "options": [
            {"text": "Normal sinus rhythm"},
            {"text": "Sinus bradycardia"},
            {"text": "First-degree AV block"},
            {"text": "Sinus tachycardia"},
        ],
        "correct_answer": 0,
        "rationale": (
            "Normal sinus rhythm has a rate of 60–100 bpm, a P wave preceding every QRS, "
            "and a PR interval of 0.12–0.20 seconds. All criteria are met here. "
            "First-degree AV block requires a PR interval > 0.20 seconds."
        ),
    },
    {
        "category_id": 1,
        "difficulty": Difficulty.easy,
        "nclex_domain": "Physiological Integrity",
        "stem": (
            "A client admitted for heart failure reports waking up at night unable to "
            "breathe and needing to sit upright to relieve it. The nurse documents this "
            "symptom as which of the following?"
        ),
        "options": [
            {"text": "Orthopnea"},
            {"text": "Paroxysmal nocturnal dyspnea"},
            {"text": "Cheyne-Stokes respiration"},
            {"text": "Kussmaul breathing"},
        ],
        "correct_answer": 1,
        "rationale": (
            "Paroxysmal nocturnal dyspnea (PND) is sudden shortness of breath that awakens "
            "a person from sleep, relieved by sitting upright. It is classic for left-sided "
            "heart failure. Orthopnea is dyspnea when lying flat but does not wake the "
            "client suddenly."
        ),
    },
    {
        "category_id": 1,
        "difficulty": Difficulty.medium,
        "nclex_domain": "Physiological Integrity",
        "stem": (
            "A client taking digoxin 0.125 mg daily reports nausea, yellow-green visual "
            "halos, and a heart rate of 52 bpm. Which action should the nurse take first?"
        ),
        "options": [
            {"text": "Administer the next scheduled digoxin dose as ordered"},
            {"text": "Hold the digoxin and notify the provider"},
            {"text": "Obtain a 12-lead ECG and administer a fluid bolus"},
            {"text": "Reassure the client that these are expected side effects"},
        ],
        "correct_answer": 1,
        "rationale": (
            "Nausea, visual disturbances (yellow-green halos), and bradycardia are classic "
            "signs of digoxin toxicity. The nurse should hold the drug and notify the "
            "provider immediately. Administering another dose is contraindicated. An ECG "
            "is appropriate but not before holding the drug."
        ),
    },
    {
        "category_id": 1,
        "difficulty": Difficulty.medium,
        "nclex_domain": "Safe and Effective Care Environment",
        "stem": (
            "A client returned from the cardiac catheterization lab 2 hours ago via femoral "
            "artery access. The nurse notes a large hematoma forming at the groin site and "
            "the client's blood pressure has dropped from 128/76 to 88/52 mmHg. What is "
            "the priority nursing action?"
        ),
        "options": [
            {"text": "Apply a pressure dressing and elevate the leg"},
            {"text": "Notify the provider and apply manual pressure to the site"},
            {"text": "Increase the IV fluid rate and obtain a stat CBC"},
            {"text": "Document findings and continue to monitor every 15 minutes"},
        ],
        "correct_answer": 1,
        "rationale": (
            "A rapidly expanding hematoma with hypotension suggests arterial bleeding — a "
            "life-threatening complication. The priority is to apply manual pressure to "
            "control bleeding and immediately notify the provider. Documentation and "
            "monitoring alone are inadequate given hemodynamic instability."
        ),
    },
    {
        "category_id": 1,
        "difficulty": Difficulty.hard,
        "nclex_domain": "Safe and Effective Care Environment",
        "stem": (
            "A nurse is caring for a client on a telemetry unit when the monitor alarms. "
            "The nurse finds the client unresponsive with no palpable pulse and the monitor "
            "shows ventricular fibrillation. After activating the emergency response system, "
            "what is the nurse's next action?"
        ),
        "options": [
            {"text": "Administer IV epinephrine 1 mg"},
            {"text": "Begin high-quality chest compressions"},
            {"text": "Deliver an immediate unsynchronized defibrillation shock"},
            {"text": "Insert an oral airway and provide bag-mask ventilation"},
        ],
        "correct_answer": 1,
        "rationale": (
            "Per AHA ACLS guidelines, CPR should begin immediately while the defibrillator "
            "is being prepared. High-quality chest compressions maintain perfusion until "
            "defibrillation is available. Defibrillation is the definitive treatment for "
            "V-fib, but compressions come first if the defibrillator is not immediately "
            "at the bedside. Epinephrine is given after the first shock attempt."
        ),
    },
    {
        "category_id": 1,
        "difficulty": Difficulty.hard,
        "nclex_domain": "Physiological Integrity",
        "stem": (
            "A post-operative client develops muffled heart sounds, distended neck veins, "
            "and hypotension. The 12-lead ECG shows low-voltage QRS complexes. Which "
            "condition does the nurse suspect, and what is the expected provider order?"
        ),
        "options": [
            {"text": "Tension pneumothorax; needle decompression"},
            {"text": "Cardiac tamponade; pericardiocentesis"},
            {"text": "Pulmonary embolism; thrombolytics"},
            {"text": "Aortic dissection; emergent CT angiography"},
        ],
        "correct_answer": 1,
        "rationale": (
            "Beck's triad (muffled heart sounds, JVD, hypotension) combined with low-voltage "
            "QRS on ECG is pathognomonic for cardiac tamponade. Pericardiocentesis to "
            "drain the pericardial fluid is the emergency treatment. Tension pneumothorax "
            "presents with tracheal deviation and absent breath sounds."
        ),
    },

    # ── Category 2: Pharmacology ──────────────────────────────────────────────
    {
        "category_id": 2,
        "difficulty": Difficulty.easy,
        "nclex_domain": "Safe and Effective Care Environment",
        "stem": (
            "Before administering a scheduled oral medication, a nurse checks the medication "
            "administration record and confirms which five rights? Select the response that "
            "lists all five correctly."
        ),
        "options": [
            {"text": "Right client, right drug, right dose, right route, right time"},
            {"text": "Right client, right drug, right dose, right form, right frequency"},
            {"text": "Right client, right drug, right route, right nurse, right time"},
            {"text": "Right drug, right dose, right route, right time, right documentation"},
        ],
        "correct_answer": 0,
        "rationale": (
            "The five rights of medication administration are: right client, right drug, "
            "right dose, right route, and right time. Some institutions add rights such as "
            "right documentation or right reason, but the classic five are those listed "
            "in option A."
        ),
    },
    {
        "category_id": 2,
        "difficulty": Difficulty.easy,
        "nclex_domain": "Physiological Integrity",
        "stem": (
            "A client on warfarin therapy has an INR of 8.2 and is experiencing active "
            "bleeding. The nurse anticipates which medication will be ordered by the provider?"
        ),
        "options": [
            {"text": "Protamine sulfate"},
            {"text": "Vitamin K (phytonadione)"},
            {"text": "Fresh frozen plasma only"},
            {"text": "Idarucizumab"},
        ],
        "correct_answer": 1,
        "rationale": (
            "Vitamin K (phytonadione) is the specific antidote for warfarin toxicity. In "
            "life-threatening bleeding, fresh frozen plasma (FFP) may also be used for "
            "rapid reversal, but vitamin K is the definitive antidote. Protamine sulfate "
            "reverses heparin. Idarucizumab reverses dabigatran."
        ),
    },
    {
        "category_id": 2,
        "difficulty": Difficulty.medium,
        "nclex_domain": "Physiological Integrity",
        "stem": (
            "A client is receiving a continuous IV heparin infusion. Which laboratory value "
            "should the nurse monitor to determine therapeutic effectiveness?"
        ),
        "options": [
            {"text": "Prothrombin time (PT)"},
            {"text": "Activated partial thromboplastin time (aPTT)"},
            {"text": "International Normalized Ratio (INR)"},
            {"text": "Platelet count"},
        ],
        "correct_answer": 1,
        "rationale": (
            "Heparin's anticoagulant effect is monitored using the aPTT. The therapeutic "
            "range is typically 1.5–2.5 times the control value (approximately 60–100 seconds). "
            "PT/INR is used to monitor warfarin. Platelet count is monitored for "
            "heparin-induced thrombocytopenia (HIT), not therapeutic effect."
        ),
    },
    {
        "category_id": 2,
        "difficulty": Difficulty.medium,
        "nclex_domain": "Physiological Integrity",
        "stem": (
            "A client is prescribed metoprolol (Lopressor) 50 mg orally twice daily. Before "
            "administering the morning dose, the nurse assesses a heart rate of 48 bpm. "
            "Which action is most appropriate?"
        ),
        "options": [
            {"text": "Administer the dose and recheck the heart rate in 30 minutes"},
            {"text": "Hold the dose and notify the provider"},
            {"text": "Administer half the dose and document findings"},
            {"text": "Administer the dose because beta-blockers lower heart rate"},
        ],
        "correct_answer": 1,
        "rationale": (
            "Beta-blockers should generally be held if the apical pulse is below 60 bpm "
            "(many institutions use 50–60 bpm as the threshold per provider standing orders). "
            "A rate of 48 warrants holding the dose and notifying the provider. Administering "
            "the full or partial dose risks further bradycardia."
        ),
    },
    {
        "category_id": 2,
        "difficulty": Difficulty.hard,
        "nclex_domain": "Physiological Integrity",
        "stem": (
            "A client with bipolar disorder has been on lithium carbonate for 6 weeks and "
            "reports coarse hand tremors, persistent nausea and vomiting, slurred speech, "
            "and muscle twitching. The serum lithium level is 2.4 mEq/L. Which action "
            "should the nurse take first?"
        ),
        "options": [
            {"text": "Encourage increased fluid intake and add a low-sodium snack"},
            {"text": "Hold lithium and prepare the client for hemodialysis if ordered"},
            {"text": "Administer the next scheduled lithium dose with food"},
            {"text": "Notify the provider and request a repeat lithium level in 4 hours"},
        ],
        "correct_answer": 1,
        "rationale": (
            "A lithium level of 2.4 mEq/L (therapeutic range 0.6–1.2 mEq/L for maintenance) "
            "represents severe toxicity. Coarse tremors, slurred speech, and muscle twitching "
            "indicate neurotoxicity requiring immediate cessation of lithium. Hemodialysis "
            "is used for life-threatening toxicity. Encouraging fluids alone is insufficient "
            "at this level."
        ),
    },
    {
        "category_id": 2,
        "difficulty": Difficulty.hard,
        "nclex_domain": "Physiological Integrity",
        "stem": (
            "A nurse is preparing a regular insulin infusion for a client in DKA. The order "
            "reads: Regular insulin 100 units in 100 mL NS; infuse at 0.1 unit/kg/hr. The "
            "client weighs 80 kg. At how many mL/hr should the nurse set the infusion pump?"
        ),
        "options": [
            {"text": "4 mL/hr"},
            {"text": "8 mL/hr"},
            {"text": "10 mL/hr"},
            {"text": "12 mL/hr"},
        ],
        "correct_answer": 1,
        "rationale": (
            "Dose = 0.1 unit/kg/hr × 80 kg = 8 units/hr. "
            "Concentration = 100 units / 100 mL = 1 unit/mL. "
            "Rate = 8 units/hr ÷ 1 unit/mL = 8 mL/hr."
        ),
    },

    # ── Category 3: Pediatric Nursing ─────────────────────────────────────────
    {
        "category_id": 3,
        "difficulty": Difficulty.easy,
        "nclex_domain": "Health Promotion and Maintenance",
        "stem": (
            "A nurse is assessing a 3-month-old infant during a well-child visit. Which "
            "heart rate would the nurse document as within the expected normal range?"
        ),
        "options": [
            {"text": "72 bpm"},
            {"text": "110 bpm"},
            {"text": "155 bpm"},
            {"text": "175 bpm"},
        ],
        "correct_answer": 1,
        "rationale": (
            "The normal resting heart rate for infants (0–12 months) is 100–160 bpm. "
            "110 bpm falls within this range. 72 bpm is normal for adults but low for "
            "an infant. 175 bpm would suggest tachycardia and requires further assessment."
        ),
    },
    {
        "category_id": 3,
        "difficulty": Difficulty.easy,
        "nclex_domain": "Physiological Integrity",
        "stem": (
            "A nurse is assessing a 2-year-old brought to the clinic with a 3-day history "
            "of vomiting and diarrhea. Which assessment finding is the most reliable "
            "indicator of dehydration in this child?"
        ),
        "options": [
            {"text": "Dry oral mucous membranes"},
            {"text": "Sunken anterior fontanel"},
            {"text": "Weight loss compared with the previous visit"},
            {"text": "Decreased skin turgor"},
        ],
        "correct_answer": 2,
        "rationale": (
            "Acute weight loss is the most reliable and objective indicator of fluid loss "
            "in pediatric clients. Each 1 kg of weight loss equals approximately 1 L of "
            "fluid lost. By age 2, the anterior fontanel is closed, making it unhelpful. "
            "Mucous membrane dryness and skin turgor are useful but more subjective."
        ),
    },
    {
        "category_id": 3,
        "difficulty": Difficulty.medium,
        "nclex_domain": "Safe and Effective Care Environment",
        "stem": (
            "A 4-year-old with a temperature of 39.8°C (103.6°F) begins having a generalized "
            "tonic-clonic seizure. What is the nurse's priority action?"
        ),
        "options": [
            {"text": "Insert an oral airway to prevent tongue biting"},
            {"text": "Restrain the child to prevent injury"},
            {"text": "Position the child on the side and protect from injury"},
            {"text": "Administer rectal diazepam immediately per standing order"},
        ],
        "correct_answer": 2,
        "rationale": (
            "During a febrile seizure the priority is to maintain safety and a patent airway "
            "by turning the child to the side (recovery position) to prevent aspiration and "
            "protect from environmental hazards. Objects should never be inserted into the "
            "mouth during a seizure. Restraint can cause injury. Anticonvulsants are not "
            "routinely recommended for simple febrile seizures."
        ),
    },
    {
        "category_id": 3,
        "difficulty": Difficulty.medium,
        "nclex_domain": "Physiological Integrity",
        "stem": (
            "A 7-year-old with asthma is in the emergency department with increased work "
            "of breathing. The child's oxygen saturation is 91% on room air and the nurse "
            "auscultates diffuse expiratory wheezing. Which intervention should be "
            "implemented first?"
        ),
        "options": [
            {"text": "Administer nebulized albuterol as ordered"},
            {"text": "Obtain arterial blood gas values"},
            {"text": "Apply a non-rebreather mask at 15 L/min"},
            {"text": "Prepare for endotracheal intubation"},
        ],
        "correct_answer": 0,
        "rationale": (
            "Short-acting beta-2 agonists (SABA) such as albuterol are the first-line "
            "bronchodilator for acute asthma exacerbations. They relieve bronchospasm rapidly. "
            "Supplemental oxygen is also indicated for SpO₂ < 94%, but albuterol addresses "
            "the underlying cause. Intubation is reserved for respiratory failure."
        ),
    },
    {
        "category_id": 3,
        "difficulty": Difficulty.hard,
        "nclex_domain": "Safe and Effective Care Environment",
        "stem": (
            "A 3-year-old is brought to the ED with acute stridor, drooling, a muffled "
            "'hot potato' voice, and high fever. The child is sitting upright and refusing "
            "to lie down. Which action is most appropriate?"
        ),
        "options": [
            {"text": "Perform a throat culture to identify the causative organism"},
            {"text": "Place the child supine and prepare for bag-mask ventilation"},
            {"text": "Keep the child calm and upright; do not examine the throat; notify "
                     "the provider immediately"},
            {"text": "Administer racemic epinephrine by nebulizer and observe for 2 hours"},
        ],
        "correct_answer": 2,
        "rationale": (
            "These are classic signs of epiglottitis, a medical emergency caused most often "
            "by Haemophilus influenzae type b. Examining the throat or agitating the child "
            "can trigger complete airway obstruction. The child should be kept calm and "
            "upright, the provider notified immediately for controlled intubation in the OR. "
            "Racemic epinephrine is used for croup (subglottic), not epiglottitis."
        ),
    },
    {
        "category_id": 3,
        "difficulty": Difficulty.hard,
        "nclex_domain": "Physiological Integrity",
        "stem": (
            "A 14-year-old with type 1 diabetes is admitted with blood glucose 520 mg/dL, "
            "pH 7.22, bicarbonate 12 mEq/L, and positive urine ketones. After establishing "
            "IV access, which intervention has the highest priority?"
        ),
        "options": [
            {"text": "Start subcutaneous insulin glargine per sliding scale"},
            {"text": "Administer IV sodium bicarbonate to correct acidosis"},
            {"text": "Begin isotonic IV fluid resuscitation"},
            {"text": "Start a continuous insulin infusion immediately"},
        ],
        "correct_answer": 2,
        "rationale": (
            "In pediatric DKA, IV fluid resuscitation with isotonic saline (0.9% NS) is "
            "the first priority to restore circulating volume and tissue perfusion. Insulin "
            "is started after 1 hour of fluid resuscitation to avoid cerebral edema from "
            "rapid osmotic shifts. Sodium bicarbonate is not routinely recommended as it "
            "can worsen cerebral edema and hypokalemia."
        ),
    },

    # ── Category 4: Maternal Health ───────────────────────────────────────────
    {
        "category_id": 4,
        "difficulty": Difficulty.easy,
        "nclex_domain": "Health Promotion and Maintenance",
        "stem": (
            "A nurse is palpating the fundus of a client who is 20 weeks gestation. At "
            "which landmark would the nurse expect to find the fundus?"
        ),
        "options": [
            {"text": "At the symphysis pubis"},
            {"text": "At the level of the umbilicus"},
            {"text": "Two fingerbreadths above the umbilicus"},
            {"text": "At the xiphoid process"},
        ],
        "correct_answer": 1,
        "rationale": (
            "At 20 weeks gestation, the fundus is expected to be at the level of the "
            "umbilicus. As a general rule, fundal height in centimeters approximates the "
            "gestational age in weeks between 20 and 36 weeks (McDonald's rule). At 20 cm "
            "the fundus reaches the umbilicus."
        ),
    },
    {
        "category_id": 4,
        "difficulty": Difficulty.easy,
        "nclex_domain": "Physiological Integrity",
        "stem": (
            "A nurse is assessing a client on postpartum day 2 after a vaginal delivery. "
            "The lochia is described as moderate in amount, dark red, and contains small "
            "clots. How should the nurse document this finding?"
        ),
        "options": [
            {"text": "Lochia alba — abnormal, requires provider notification"},
            {"text": "Lochia serosa — expected at this stage"},
            {"text": "Lochia rubra — expected for postpartum day 1–3"},
            {"text": "Lochia rubra — abnormal; clots indicate hemorrhage"},
        ],
        "correct_answer": 2,
        "rationale": (
            "Lochia rubra (dark red, bloody) is normal for the first 1–3 days postpartum. "
            "Small clots can be normal. Lochia serosa (pinkish-brown, serous) appears days "
            "4–10. Lochia alba (creamy yellow-white) appears after day 10. Large clots "
            "(> golf ball size) or saturating a pad in < 1 hour would be abnormal."
        ),
    },
    {
        "category_id": 4,
        "difficulty": Difficulty.medium,
        "nclex_domain": "Physiological Integrity",
        "stem": (
            "A client at 34 weeks gestation presents with a blood pressure of 158/106 mmHg "
            "on two readings 4 hours apart, 3+ proteinuria on dipstick, and reports a "
            "severe frontal headache with visual changes. Which assessment finding requires "
            "the most immediate intervention?"
        ),
        "options": [
            {"text": "Proteinuria of 3+"},
            {"text": "Blood pressure of 158/106 mmHg"},
            {"text": "Severe headache with visual changes"},
            {"text": "Gestational age of 34 weeks"},
        ],
        "correct_answer": 2,
        "rationale": (
            "Severe headache and visual changes (scotoma, blurred vision) in a client with "
            "severe-range blood pressure are warning signs of impending eclampsia and "
            "cerebral involvement. These neurological symptoms signal the highest immediate "
            "risk. Hypertension and proteinuria confirm severe preeclampsia but the "
            "neurological symptoms represent the most time-sensitive finding."
        ),
    },
    {
        "category_id": 4,
        "difficulty": Difficulty.medium,
        "nclex_domain": "Safe and Effective Care Environment",
        "stem": (
            "A nurse notes that a client who delivered vaginally 30 minutes ago has saturated "
            "two perineal pads in 15 minutes. The fundus is boggy and displaced to the right. "
            "Which action should the nurse take first?"
        ),
        "options": [
            {"text": "Insert a urinary catheter to relieve bladder distension"},
            {"text": "Perform fundal massage and have the client void or catheterize"},
            {"text": "Increase the oxytocin infusion rate per standing orders"},
            {"text": "Notify the provider and prepare the client for surgery"},
        ],
        "correct_answer": 1,
        "rationale": (
            "A boggy, displaced fundus is the classic presentation of uterine atony "
            "complicated by bladder distension — the most common cause of early postpartum "
            "hemorrhage. The first interventions are fundal massage and bladder emptying. "
            "A full bladder prevents the uterus from contracting effectively. Oxytocin "
            "augmentation and provider notification follow if massage and voiding fail."
        ),
    },
    {
        "category_id": 4,
        "difficulty": Difficulty.hard,
        "nclex_domain": "Safe and Effective Care Environment",
        "stem": (
            "A client at 38 weeks develops a tonic-clonic seizure. She has been diagnosed "
            "with severe preeclampsia. The nurse has administered magnesium sulfate as "
            "prescribed. Which assessment finding would indicate magnesium toxicity, "
            "requiring the nurse to hold the infusion immediately?"
        ),
        "options": [
            {"text": "Urinary output of 35 mL/hr"},
            {"text": "Respiratory rate of 10 breaths/min"},
            {"text": "Deep tendon reflexes rated 2+"},
            {"text": "Serum magnesium level of 5 mEq/L"},
        ],
        "correct_answer": 1,
        "rationale": (
            "Respiratory rate < 12 breaths/min is a critical sign of magnesium toxicity "
            "and requires immediate cessation of the infusion and administration of calcium "
            "gluconate (the antidote). Loss of deep tendon reflexes (areflexia) is the "
            "earliest sign; respiratory depression is the most dangerous. A urine output "
            "of 30 mL/hr or more is acceptable. Therapeutic magnesium levels are 4–7 mEq/L."
        ),
    },
    {
        "category_id": 4,
        "difficulty": Difficulty.hard,
        "nclex_domain": "Physiological Integrity",
        "stem": (
            "A client at 32 weeks gestation presents with sudden, severe upper right "
            "quadrant pain, nausea, elevated liver enzymes (AST 250 U/L, ALT 220 U/L), "
            "platelets of 82,000/mm³, and hemolysis on peripheral smear. Which condition "
            "does the nurse recognize?"
        ),
        "options": [
            {"text": "Acute cholecystitis"},
            {"text": "Severe preeclampsia without HELLP"},
            {"text": "HELLP syndrome"},
            {"text": "Acute fatty liver of pregnancy"},
        ],
        "correct_answer": 2,
        "rationale": (
            "HELLP syndrome is defined by Hemolysis (H), Elevated Liver enzymes (EL), and "
            "Low Platelet count (LP). RUQ pain results from hepatic capsule distension. "
            "Platelets < 100,000 and elevated transaminases confirm the diagnosis. HELLP "
            "is a severe variant of preeclampsia requiring immediate delivery consideration "
            "regardless of gestational age."
        ),
    },

    # ── Category 5: Mental Health ─────────────────────────────────────────────
    {
        "category_id": 5,
        "difficulty": Difficulty.easy,
        "nclex_domain": "Psychosocial Integrity",
        "stem": (
            "A client tells the nurse, 'I feel like no one in my family cares about me.' "
            "Which response best demonstrates a therapeutic communication technique?"
        ),
        "options": [
            {"text": "'I'm sure your family loves you very much.'"},
            {"text": "'Tell me more about what makes you feel that way.'"},
            {"text": "'Why would you think that? Have you talked to them?'"},
            {"text": "'Everyone goes through times when family relationships are hard.'"},
        ],
        "correct_answer": 1,
        "rationale": (
            "Asking the client to elaborate ('Tell me more') is a broad opening/exploring "
            "technique that encourages the client to express feelings without judgment. "
            "Option A offers false reassurance. Option C uses 'why' which can feel "
            "accusatory and puts the client on the defensive. Option D is a minimizing "
            "response that dismisses the client's unique experience."
        ),
    },
    {
        "category_id": 5,
        "difficulty": Difficulty.easy,
        "nclex_domain": "Psychosocial Integrity",
        "stem": (
            "A nurse is caring for four clients on an inpatient psychiatric unit. Using "
            "Maslow's hierarchy of needs, which client should be assessed first?"
        ),
        "options": [
            {"text": "A client with schizophrenia who states, 'I am hearing voices.'"},
            {"text": "A client with depression who has not showered in 3 days"},
            {"text": "A client with anorexia nervosa whose heart rate is 44 bpm"},
            {"text": "A client with anxiety requesting relaxation exercises"},
        ],
        "correct_answer": 2,
        "rationale": (
            "Physiological needs are the foundation of Maslow's hierarchy. A heart rate "
            "of 44 bpm represents a life-threatening bradycardia — a physiological "
            "emergency that takes priority over psychological or safety needs. Hearing "
            "voices and poor self-care are serious but not immediately life-threatening."
        ),
    },
    {
        "category_id": 5,
        "difficulty": Difficulty.medium,
        "nclex_domain": "Psychosocial Integrity",
        "stem": (
            "A nurse is admitting a client with schizophrenia who is agitated, pacing, "
            "and responding to internal stimuli. Which assessment is the nurse's priority?"
        ),
        "options": [
            {"text": "Determine the content of the auditory hallucinations"},
            {"text": "Assess whether the client has command hallucinations to harm self or others"},
            {"text": "Review the client's medication history for antipsychotic compliance"},
            {"text": "Establish a therapeutic relationship by engaging the client in conversation"},
        ],
        "correct_answer": 1,
        "rationale": (
            "Safety is the priority. Command hallucinations (voices ordering the client to "
            "harm themselves or others) represent an immediate danger requiring intervention. "
            "While understanding the hallucination content and medication history are "
            "important, establishing safety supersedes all other assessments at this point."
        ),
    },
    {
        "category_id": 5,
        "difficulty": Difficulty.medium,
        "nclex_domain": "Physiological Integrity",
        "stem": (
            "A client with bipolar disorder is started on lithium carbonate. Which "
            "instruction should the nurse include in the discharge teaching?"
        ),
        "options": [
            {"text": "Decrease sodium intake to enhance lithium reabsorption"},
            {"text": "Maintain consistent fluid and sodium intake; avoid major dietary changes"},
            {"text": "Take lithium only when experiencing manic symptoms"},
            {"text": "Stop lithium immediately if fine hand tremors develop"},
        ],
        "correct_answer": 1,
        "rationale": (
            "Lithium and sodium compete for renal reabsorption. A low-sodium diet causes "
            "the kidneys to retain lithium, increasing the risk of toxicity. Consistent "
            "sodium and fluid intake keeps lithium levels stable. Lithium must be taken "
            "regularly, not PRN. Fine tremors are an expected early side effect, not a "
            "reason to stop the medication."
        ),
    },
    {
        "category_id": 5,
        "difficulty": Difficulty.hard,
        "nclex_domain": "Physiological Integrity",
        "stem": (
            "A client was started on a selective serotonin reuptake inhibitor (SSRI) two "
            "weeks ago and the dose was increased yesterday. The client now presents to the "
            "ED with agitation, diaphoresis, hyperthermia (38.9°C), clonus, and hyperreflexia. "
            "Which condition does the nurse suspect?"
        ),
        "options": [
            {"text": "Neuroleptic malignant syndrome (NMS)"},
            {"text": "Serotonin syndrome"},
            {"text": "Anticholinergic toxicity"},
            {"text": "Malignant hyperthermia"},
        ],
        "correct_answer": 1,
        "rationale": (
            "Serotonin syndrome typically presents within hours of a dose increase or "
            "addition of a serotonergic drug and is characterized by the triad of mental "
            "status changes, autonomic instability, and neuromuscular abnormalities (clonus, "
            "hyperreflexia). NMS is associated with antipsychotics, has a slower onset, "
            "and features lead-pipe rigidity rather than clonus. Malignant hyperthermia "
            "occurs with volatile anesthetics."
        ),
    },
    {
        "category_id": 5,
        "difficulty": Difficulty.hard,
        "nclex_domain": "Safe and Effective Care Environment",
        "stem": (
            "A client receiving haloperidol decanoate develops a temperature of 40.1°C, "
            "severe muscle rigidity, diaphoresis, altered consciousness, and a creatine "
            "kinase (CK) of 12,000 U/L. Which action is the nurse's highest priority?"
        ),
        "options": [
            {"text": "Administer a PRN dose of lorazepam for agitation"},
            {"text": "Discontinue the antipsychotic, notify the provider, and transfer "
                     "to an intensive care setting"},
            {"text": "Apply cooling blankets and monitor temperature every 2 hours"},
            {"text": "Administer antipyretics and increase oral fluid intake"},
        ],
        "correct_answer": 1,
        "rationale": (
            "This presentation is classic neuroleptic malignant syndrome (NMS) — a rare "
            "but potentially fatal reaction to antipsychotics. The priority is to "
            "immediately discontinue the offending agent, notify the provider, and arrange "
            "ICU-level care. Supportive measures (cooling, hydration, dantrolene for "
            "rigidity, bromocriptine) are initiated in the ICU. Administering more "
            "benzodiazepines alone is insufficient; the antipsychotic must be stopped."
        ),
    },
]


async def seed():
    async with SessionLocal() as db:
        admin = await db.scalar(select(User).where(User.email == "admin@tricore.app"))
        if not admin:
            raise RuntimeError("Admin user not found — run seed.py first.")

        for q in QUESTIONS:
            db.add(
                Question(
                    stem=q["stem"],
                    options=q["options"],
                    correct_answer=q["correct_answer"],
                    rationale=q["rationale"],
                    category_id=q["category_id"],
                    nclex_domain=q["nclex_domain"],
                    difficulty=q["difficulty"],
                    status=QStatus.published,
                    created_by=admin.id,
                )
            )
        await db.commit()
        print(f"Seeded {len(QUESTIONS)} questions.")


asyncio.run(seed())
