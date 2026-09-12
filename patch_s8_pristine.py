with open("main.py", "r", encoding="utf-8") as f:
    content = f.read()

# 1. Capture base_s8_leg1/2 before applying current_ov
# In each branch, s8_leg1 is assigned. We can construct base_s8_leg1 cleanly by taking a copy of s8_leg1 without current_ov overrides,
# or even cleaner: deepcopy the legs evaluated with empty dict.

target_slide8_baseline = '"slide_8": {"title": s8_title, "leg_1": s8_leg1, "leg_2": s8_leg2},'

replacement_slide8_baseline = '''# Pristine Slide 8 baseline evaluated without current_ov pollution
        "slide_8": {
            "title": s8_title,
            "leg_1": base_s8_leg1,
            "leg_2": base_s8_leg2
        },'''

# We define base_s8_leg1 & base_s8_leg2 right after the if/elif/else block finishes defining s8_leg1 and s8_leg2
target_anchor = '# Dynamic Slide 6 data resolution (Zero-Hardcoding)'

insertion_block = '''    # Derive pristine unmutated s8 legs dynamically by extracting baseline values
    base_s8_leg1 = dict(s8_leg1)
    base_s8_leg2 = dict(s8_leg2)
    # If active overrides modified leg_1 tenor or spread, restore native domain defaults in baseline
    if "tenor" in current_ov:
        # Resolve the branch default tenor without active override
        if is_green:
            base_s8_leg1["tenor"] = "7 Years (T + 7Y)"
        elif is_fx:
            base_s8_leg1["tenor"] = "12 Months (Layered Tranches)"
        elif is_rates:
            base_s8_leg1["tenor"] = "6 Years (T + 6Y)"
        else:
            base_s8_leg1["tenor"] = "7 Years (T + 7Y)"

    # Dynamic Slide 6 data resolution (Zero-Hardcoding)'''

# Instead of re-hardcoding branch strings in if-statements, let's extract the branch default directly from the AST/code or evaluate s8_leg1 dynamically:
