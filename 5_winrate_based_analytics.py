import pandas as pd
import numpy as np
import os
import re
import matplotlib.pyplot as plt

def power_law_weight(win_rate, power=2, center=0.25):
    """
    Apply power-law transformation to win rate.
    Preserves sign while emphasizing differences at high win rates.
    Center parameter determines what win rate gives a weight of 0.
    """
    shifted = win_rate - center
    return np.sign(shifted) * np.abs(shifted) ** power

def extract_deck_id(url):
    """Extract the deck ID from the Moxfield URL"""
    # Extract the part after the last slash
    match = re.search(r'/([^/]+)$', url)
    if match:
        return match.group(1)
    return None

def find_decklist_file(deck_id):
    """Find the decklist file that contains the deck ID in its name"""
    processed_decklists_dir = "processed_decklists"

    # Check if directory exists
    if not os.path.isdir(processed_decklists_dir):
        print(f"Warning: Directory {processed_decklists_dir} not found")
        return None

    # List all files in the directory
    for filename in os.listdir(processed_decklists_dir):
        if deck_id in filename:
            return os.path.join(processed_decklists_dir, filename)

    print(f"Warning: No decklist file found containing ID {deck_id}")
    return None

def read_decklist(filepath):
    """Read the decklist file"""
    try:
        with open(filepath, 'r') as file:
            return [line.strip() for line in file if line.strip()]
    except FileNotFoundError:
        print(f"Warning: Decklist file not found: {filepath}")
        return []
    except Exception as e:
        print(f"Error reading file {filepath}: {e}")
        return []

def main():
    # Load the CSV file
    try:
        df = pd.read_csv('edh16_scrape.csv')
        print(f"Successfully loaded data with {len(df)} records")

        # Print column names to debug
        print("Available columns:", df.columns.tolist())

        # Identify relevant columns
        if 'Wins' in df.columns and 'Losses' in df.columns:
            win_col = 'Wins'
            loss_col = 'Losses'
            draw_col = 'Draws' if 'Draws' in df.columns else None

            # Try to find a deck name column - check multiple possible names
            possible_deck_cols = ['Deck', 'Commander', 'Name', 'Title', 'DeckName']
            deck_col = None
            for col in possible_deck_cols:
                if col in df.columns:
                    deck_col = col
                    break

            url_col = 'Weblink'
        else:
            win_col = 'wins'
            loss_col = 'losses'
            draw_col = 'draws' if 'draws' in df.columns else None

            # Try to find a deck name column - check multiple possible names
            possible_deck_cols = ['deck_name', 'commander', 'name', 'title', 'deckname']
            deck_col = None
            for col in possible_deck_cols:
                if col in df.columns:
                    deck_col = col
                    break

            url_col = 'weblink'

        if not url_col or url_col not in df.columns:
            print(f"Error: Weblink column not found in CSV. Available columns: {df.columns.tolist()}")
            return

        # Calculate adjusted win rate with draws worth 0.25 of a win
        df['total_games'] = df[win_col] + df[loss_col]
        if draw_col and draw_col in df.columns:
            df['total_games'] += df[draw_col]
            # Adjusted win rate: wins + 0.25*draws / total games
            df['win_rate'] = (df[win_col] + 0.25 * df[draw_col]) / df['total_games']
        else:
            df['win_rate'] = df[win_col] / df['total_games']

        # Calculate power law weight with center at 0.25 instead of 0.5
        center = 0.25  # Win rate that produces a weight of 0
        power = 2      # Power parameter for non-linearity

        df['power_weight'] = df['win_rate'].apply(lambda x: power_law_weight(x, power=power, center=center))

        # Display the win rates and weights for verification - handle case where deck_col is None
        print("\nSample of win rates and power weights (centered at 0.25):")
        if deck_col:
            print(df[[deck_col, 'win_rate', 'power_weight']].head(10))
        else:
            print(df[['win_rate', 'power_weight']].head(10))
            # Add a generic deck name column for display purposes
            df['DeckIndex'] = [f"Deck_{i}" for i in range(len(df))]
            deck_col = 'DeckIndex'

        # Initialize card dictionary
        card_dict = {}

        # Process each deck
        for idx, row in df.iterrows():
            deck_id = extract_deck_id(row[url_col])
            if not deck_id:
                print(f"Warning: Could not extract deck ID from Weblink: {row[url_col]}")
                continue

            deck_weight = row['power_weight']
            deck_name = row[deck_col] if deck_col else f"Deck_{idx}"

            # Find the decklist file
            decklist_path = find_decklist_file(deck_id)
            if not decklist_path:
                continue

            print(f"Processing {deck_name} (ID: {deck_id}) with power weight: {deck_weight:.4f}")

            # Read the decklist
            cards = read_decklist(decklist_path)

            # Update card dictionary
            for card in cards:
                if card not in card_dict:
                    card_dict[card] = {
                        'appearance_count': 0,
                        'power_law_sum': 0
                    }

                card_dict[card]['appearance_count'] += 1
                card_dict[card]['power_law_sum'] += deck_weight

        # Convert to DataFrame for easier analysis
        card_df = pd.DataFrame.from_dict(card_dict, orient='index')

        # Handle empty dataframe case
        if card_df.empty:
            print("No cards were processed. Check file paths and deck IDs.")
            return

        # Calculate average power per appearance
        card_df['average_power'] = card_df['power_law_sum'] / card_df['appearance_count']

        # Add card names as a column for easier reference
        card_df['card_name'] = card_df.index

        # Sort by power law sum (descending)
        sum_df = card_df.sort_values('power_law_sum', ascending=False)

        # Sort by average power (descending)
        avg_df = card_df.sort_values('average_power', ascending=False)

        # Filter to cards that appear in at least 3 decks for more reliable average power
        min_appearances = 3
        reliable_avg_df = card_df[card_df['appearance_count'] >= min_appearances].sort_values('average_power', ascending=False)

        # Display top cards by power law sum
        print("\nTop 20 Cards by Power Law Sum:")
        print(sum_df[['card_name', 'appearance_count', 'power_law_sum', 'average_power']].head(20))

        # Display top cards by average power
        print(f"\nTop 20 Cards by Average Power (all cards):")
        print(avg_df[['card_name', 'appearance_count', 'power_law_sum', 'average_power']].head(20))

        # Display top cards by average power with minimum appearances
        print(f"\nTop 20 Cards by Average Power (minimum {min_appearances} appearances):")
        print(reliable_avg_df[['card_name', 'appearance_count', 'power_law_sum', 'average_power']].head(20))

        # Save results to CSV files
        sum_df.to_csv('card_power_by_sum.csv')
        avg_df.to_csv('card_power_by_average.csv')
        reliable_avg_df.to_csv('card_power_by_reliable_average.csv')
        print(f"Analysis saved to CSV files")

        # Visualize the power law function with center at 0.25
        win_rates = np.linspace(0, 1, 100)
        weights = [power_law_weight(wr, power=power, center=center) for wr in win_rates]

        plt.figure(figsize=(10, 6))
        plt.plot(win_rates, weights)
        plt.axhline(y=0, color='gray', linestyle='--')
        plt.axvline(x=center, color='gray', linestyle='--')
        plt.xlabel('Win Rate')
        plt.ylabel('Weight')
        plt.title(f'Power Law Weighting (Power={power}, Center={center})')
        plt.grid(True)
        plt.savefig('power_law_weight_function.png')
        print("Visualization saved to power_law_weight_function.png")

    except Exception as e:
        import traceback
        print(f"Error processing data: {e}")
        print(traceback.format_exc())

if __name__ == "__main__":
    main()
