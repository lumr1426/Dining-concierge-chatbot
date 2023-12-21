import json

# Load the existing JSON data
with open('thai restaurants.json', 'r') as input_file:
    data = json.load(input_file)

# Create a list to store the modified data
modified_data = []

# Iterate through the original data
for entry in data:
    # Add the Elasticsearch-style metadata
    metadata = {
        "index": {
            "_index": "restaurants",
            "_id": entry["id"]
        }
    }
    metadata2 = {
        "restaurant_id": entry["id"],
        "cuisine": "thai"
    }

    # Append the modified entry to the list
    modified_data.append(metadata)
    modified_data.append(metadata2)

# Save the modified data as a JSON file
with open('thai_output_data.json', 'w') as output_file:
    for entry in modified_data:
        # Write each entry to the file
        json.dump(entry, output_file)
        output_file.write('\n')  # Add a newline between entries

print("Output JSON file created with the desired format.")
