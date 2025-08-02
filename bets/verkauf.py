import streamlit as st
from statistics import mean

# Phase 1: Bid Recommendation
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

# Phase 2: Smarter Property Recommendation with Global Play Tracking
def smart_property_recommendation(owned_properties, value_cards, all_played_properties):
    # Only consider your properties that haven't been played yet
    my_unplayed = sorted(list(set(owned_properties) - set(all_played_properties)))
    if not my_unplayed:
        return None, "You have no unplayed property cards left."

    # Compute all property cards still in play (for any player)
    all_property_cards = set(range(1, 31))
    in_play_properties = sorted(list(all_property_cards - set(all_played_properties)))

    values = sorted(value_cards)
    spread = values[-1] - values[0]

    my_best = my_unplayed[-1]
    my_worst = my_unplayed[0]
    best_in_play = in_play_properties[-1]
    worst_in_play = in_play_properties[0]

    # If your best card is the best in the game, you can guarantee top value
    if my_best == best_in_play:
        return my_best, (
            f"Your highest property ({my_best}) is the strongest left in the game. "
            f"Play it now to guarantee the top value card ({values[-1]})."
        )
    # If your worst card is the lowest in the game and a 'garbage' value exists, sacrifice it
    elif my_worst == worst_in_play and values[0] < values[1] - 2:
        return my_worst, (
            f"Your lowest property ({my_worst}) is the weakest left, and the lowest value card "
            f"({values[0]}) is much worse than the rest. Sacrifice your lowest."
        )
    # If all values are similar, play a mid property
    elif spread < 4:
        mid = my_unplayed[len(my_unplayed)//2]
        return mid, (
            f"All value cards are similar ({values}), so play a mid property ({mid})."
        )
    # Otherwise, play high but not necessarily your very best unless there are only strong values
    else:
        if len(my_unplayed) > 1 and my_unplayed[-1] > my_unplayed[-2] + 2:
            return my_unplayed[-1], (
                f"Your highest property ({my_unplayed[-1]}) is strong; use it to try for the top value ({values[-1]})."
            )
        else:
            return my_unplayed[-2] if len(my_unplayed) > 1 else my_unplayed[0], (
                f"Play your second highest property "
                f"({my_unplayed[-2] if len(my_unplayed) > 1 else my_unplayed[0]}), saving your best for a bigger round."
            )

# Streamlit UI
st.set_page_config(page_title="For Sale Bid & Play Advisor", page_icon="🏠")

st.title("🏠 For Sale: Bid & Property Play Recommendation")
st.markdown(
    "Enter the current state for both phases to get optimal bidding and play suggestions."
)

# PHASE 1: Bidding
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

# PHASE 2: Property Play
st.header("Phase 2: Property Play Recommendation")
owned_properties = st.text_input("Your owned property cards (comma-separated)", "4, 9, 17, 21, 28")
value_cards = st.text_input("Value cards revealed this round (5, comma-separated)", "1, 3, 6, 8, 10")
all_played_properties = st.text_input(
    "Property cards already played by any player (comma-separated, optional)", ""
)

try:
    owned_list = sorted([int(x.strip()) for x in owned_properties.split(",") if x.strip()])
    value_list = sorted([int(x.strip()) for x in value_cards.split(",") if x.strip()])
    played_list = sorted([int(x.strip()) for x in all_played_properties.split(",") if x.strip()])
    if len(value_list) != 5 or len(owned_list) == 0:
        st.info("Enter exactly 5 value cards and your current owned property cards.")
    else:
        prop, reasoning = smart_property_recommendation(owned_list, value_list, played_list)
        if prop is None:
            st.warning(reasoning)
        else:
            st.success(f"💡 Recommended Property to Play: **{prop}**")
            st.write(f"**Reasoning:** {reasoning}")
except ValueError:
    st.error("Please enter valid integers for Phase 2 (properties and value cards).")
