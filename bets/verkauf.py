import streamlit as st
from statistics import mean

# --- Phase 1: Bid Recommendation ---
def recommend_bid(table_cards, seen_cards=[]):
    if len(table_cards) != 5:
        return "Error: Provide exactly 5 table cards for this round."
    all_cards = set(range(1, 31))
    unseen_cards = list(all_cards - set(seen_cards) - set(table_cards))
    top = max(table_cards)
    second = sorted(table_cards)[-2]
    worst = min(table_cards)
    unseen_avg = mean(unseen_cards) if unseen_cards else 15.5
    top_delta = top - unseen_avg
    second_delta = second - unseen_avg
    spread = top - worst
    score = top_delta + 0.5 * second_delta + 0.1 * spread
    if score >= 12:
        return 4
    elif score >= 8:
        return 2
    elif score >= 4:
        return 1
    else:
        return 0

# --- Phase 2: Smart Property Recommendation ---
def smart_property_recommendation(owned_properties, value_cards):
    owned = sorted(owned_properties)
    values = sorted(value_cards)
    spread = values[-1] - values[0]
    # "Garbage" value present: lowest value much lower than others
    if values[0] < values[1] - 2 and owned:
        # Sacrifice your lowest property
        return owned[0], (
            f"Sacrifice your lowest property ({owned[0]}) "
            f"since the lowest value card ({values[0]}) is much worse than the rest."
        )
    elif spread < 4:
        # All values similar, play a mid card
        mid = owned[len(owned)//2]
        return mid, (
            f"All value cards are similar ({values}), so play a mid property ({mid})."
        )
    else:
        # High value at stake, consider playing high property
        if owned[-1] > owned[-2] + 2:
            return owned[-1], (
                f"Use your highest property ({owned[-1]}) to try for the top value ({values[-1]})."
            )
        else:
            # Play a high but not your very best
            return owned[-2], (
                f"Play your second highest property ({owned[-2]}), saving your best for a bigger spread."
            )

# --- Streamlit Layout ---
st.set_page_config(page_title="For Sale Bid & Play Advisor", page_icon="🏠")

st.title("🏠 For Sale: Bid & Property Play Recommendation")
st.markdown(
    "Enter the current state for both phases to get optimal bidding and play suggestions."
)

# --- Phase 1: Bidding ---
st.header("Phase 1: Bidding Recommendation")
table_cards = st.text_input("Property cards revealed this round (5, comma-separated)", "4, 9, 17, 21, 28")
seen_cards = st.text_input("Property cards already seen (comma-separated)", "1, 3, 6, 8, 10, 12, 14")

try:
    table_list = sorted([int(x.strip()) for x in table_cards.split(",") if x.strip()])
    seen_list = sorted([int(x.strip()) for x in seen_cards.split(",") if x.strip()])
    if len(table_list) != 5:
        st.error("Please enter exactly 5 property cards for the current round.")
    else:
        bid = recommend_bid(table_list, seen_list)
        st.success(f"💡 Recommended Bid: **{bid}**")
except ValueError:
    st.error("Please enter valid integers for Phase 1 (property cards).")

st.divider()

# --- Phase 2: Property Play ---
st.header("Phase 2: Property Play Recommendation")
owned_properties = st.text_input("Your owned property cards (comma-separated)", "4, 9, 17, 21, 28")
value_cards = st.text_input("Value cards revealed this round (5, comma-separated)", "1, 3, 6, 8, 10")

try:
    owned_list = sorted([int(x.strip()) for x in owned_properties.split(",") if x.strip()])
    value_list = sorted([int(x.strip()) for x in value_cards.split(",") if x.strip()])
    if len(value_list) != 5 or len(owned_list) == 0:
        st.info("Enter exactly 5 value cards and your current owned property cards.")
    else:
        prop, reasoning = smart_property_recommendation(owned_list, value_list)
        st.success(f"💡 Recommended Property to Play: **{prop}**")
        st.write(f"**Reasoning:** {reasoning}")
except ValueError:
    st.error("Please enter valid integers for Phase 2 (properties and value cards).")
