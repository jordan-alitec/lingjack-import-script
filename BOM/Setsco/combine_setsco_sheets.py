#!/usr/bin/env python3
"""
Script to combine all sheets from Setsco.xlsx into a single combined Excel file.

Requirements:
- Extract columns: Com No, Start, End, Location, Location2
- Remove rows where both Start and End are empty
- Set Com No column as text format
- Process all sheets with Location column (handles different header rows)
"""

import pandas as pd
import openpyxl
import sys
import os


def is_location2_value(val):
    """Check if value looks like Location2 (e.g., A01C4, A25C1)"""
    if pd.isna(val):
        return False
    val_str = str(val).strip()
    # Pattern: alphanumeric code like A01C4, A25C1, A02C3, A01C2L2
    if len(val_str) >= 4 and val_str[0].isalpha():
        # Has both letters and numbers
        if any(c.isdigit() for c in val_str) and any(c.isalpha() for c in val_str):
            # Exclude PWO codes
            if not val_str.startswith('PWO'):
                return True
    return False


def process_sheet(file_path, sheet_name, header_row=3):
    """
    Process a single sheet and extract required columns.
    
    Args:
        file_path: Path to the Excel file
        sheet_name: Name of the sheet to process
        header_row: Row number to use as header (0-indexed)
    
    Returns:
        DataFrame with columns: Com No, Start, End, Location, Location2, Sheet Name
    """
    try:
        # Read the sheet with specified header row
        df = pd.read_excel(file_path, sheet_name=sheet_name, header=header_row, skiprows=0)
        
        # Check if 'Location' column exists
        if 'Location' not in df.columns:
            return None
        
        # Clean up - remove empty rows
        df = df.dropna(how='all')
        
        # Remove header rows that appear in data
        df = df[df['Location'].astype(str).str.lower() != 'location']
        
        # Reset index to ensure proper alignment when creating result_df
        df = df.reset_index(drop=True)
        
        result_df = pd.DataFrame()
        
        # Com No - extract from Unnamed: 1 column
        if 'Com' in df.columns:
            com_no_list = []
            for val in df['Com']:
                if pd.isna(val):
                    com_no_list.append('')
                else:
                    try:
                        # Convert to string, handling both numeric and string values
                        if isinstance(val, (int, float)) and not pd.isna(val):
                            com_no_list.append(str(int(val)))
                        else:
                            com_no_list.append(str(val))
                    except:
                        com_no_list.append(str(val))
            result_df['Com No'] = com_no_list
        else:
            result_df['Com No'] = ['' for _ in range(len(df))]
        
        # Start - use .values to avoid index alignment issues
        if 'Start' in df.columns:
            result_df['Start'] = df['Start'].values
        else:
            result_df['Start'] = None
        
        # End - use .values to avoid index alignment issues
        if 'End' in df.columns:
            result_df['End'] = df['End'].values
        else:
            result_df['End'] = None
        
        # Location - use .values to avoid index alignment issues
        result_df['Location'] = df['Location'].values
        
        # Location2 - find the column that contains Location2 values
        location2_list = []
        location2_col = None
        
        # Check common columns that might contain Location2
        potential_cols = ['SYSTEM', 'Sys', 'System', 'Unnamed: 8', 'Unnamed: 7', 'Unnamed: 9']
        
        for col in df.columns:
            if col in potential_cols:
                # Check if this column has Location2 values
                for val in df[col].dropna():
                    if is_location2_value(val):
                        location2_col = col
                        break
                if location2_col:
                    break
        
        # If not found in common columns, search all columns
        if location2_col is None:
            for col in df.columns:
                if col in ['Location', 'Start', 'End', 'Com No', 'Batch']:
                    continue
                for val in df[col].dropna():
                    if is_location2_value(val):
                        location2_col = col
                        break
                if location2_col:
                    break
        
        # Extract Location2 values - use .values to avoid index alignment issues
        if location2_col:
            for val in df[location2_col].values:
                if is_location2_value(val):
                    location2_list.append(str(val).strip())
                else:
                    location2_list.append('')
        else:
            location2_list = ['' for _ in range(len(df))]
        
        result_df['Location2'] = location2_list
        
        # Add Sheet Name column
        result_df['Sheet Name'] = sheet_name.split('- ')[1].strip()

        # Remove rows where Location is NaN first
        result_df = result_df[result_df['Location'].notna()]
        
        # Then remove rows where BOTH Start and End are empty
        result_df = result_df.dropna(subset=['Start', 'End'], how='all')
        
        # Return even if empty - let the caller decide
        return result_df, location2_col
        
    except Exception as e:
        import traceback
        print(f"  ✗ Error processing {sheet_name}: {e}")
        print(f"    Traceback: {traceback.format_exc()}")
        return None, None


def combine_setsco_sheets(input_file, output_file):
    """
    Combine all sheets from Setsco.xlsx into a single Excel file.
    
    Args:
        input_file: Path to input Excel file (Setsco.xlsx)
        output_file: Path to output Excel file (Setsco_Combined.xlsx)
    """
    if not os.path.exists(input_file):
        print(f"Error: Input file '{input_file}' not found!")
        return False
    
    print("="*80)
    print("COMBINING SETSCO SHEETS")
    print("="*80)
    print(f"\nInput file: {input_file}")
    print(f"Output file: {output_file}\n")
    
    # Load workbook to get sheet names
    wb = openpyxl.load_workbook(input_file)
    sheet_names = wb.sheetnames
    
    # Define header row for each sheet (most use row 3, but some are different)
    sheet_headers = {
        'HR - 03071700': 6,
        'FH - 0307200': 4,
    }
    
    print(f"Found {len(sheet_names)} sheets in Excel file\n")
    print("Processing sheets...\n")
    
    all_dataframes = []
    processed_sheets = []
    
    for sheet_name in sheet_names:
        # Determine header row for this sheet
        header_row = sheet_headers.get(sheet_name, 3)
        
        result_df, location2_col = process_sheet(input_file, sheet_name, header_row)
        
        if result_df is not None and len(result_df) > 0:
            all_dataframes.append(result_df)
            loc2_count = sum(1 for x in result_df['Location2'] if x != '')
            processed_sheets.append(sheet_name)
            print(f"✓ {sheet_name}: {len(result_df)} rows, Location2: {loc2_count} "
                  f"(header row: {header_row}, Location2 col: {location2_col})")
        else:
            print(f"✗ {sheet_name}: No data or no Location column (skipped)")
    
    if not all_dataframes:
        print("\n✗ No data to combine!")
        return False
    
    # Combine all dataframes
    print("\nCombining all dataframes...")
    combined_df = pd.concat(all_dataframes, ignore_index=True)
    
    # Remove completely empty rows
    combined_df = combined_df.dropna(how='all')
    
    # Final filter: Remove rows where BOTH Start and End are empty
    combined_df = combined_df[~(combined_df['Start'].isna() & combined_df['End'].isna())]
    
    # Reorder columns: Com No, Start, End, Location, Location2, Sheet Name
    final_columns = ['Com No', 'Start', 'End', 'Location', 'Location2', 'Sheet Name']
    combined_df = combined_df[final_columns]
    
    # Ensure Com No and Location2 are strings with empty strings for missing values
    combined_df['Com No'] = combined_df['Com No'].apply(
        lambda x: '' if (pd.isna(x) or str(x) in ['None', 'nan', 'NaN']) else str(x)
    )
    combined_df['Location2'] = combined_df['Location2'].apply(
        lambda x: '' if (pd.isna(x) or str(x) in ['None', 'nan', 'NaN']) else str(x)
    )
    
    # Sort by Location
    print("Sorting by Location...")
    combined_df = combined_df.sort_values(by='Location', ascending=True, na_position='last')
    combined_df = combined_df.reset_index(drop=True)
    
    # Create Excel file with proper formatting
    print(f"\nSaving to {output_file}...")
    with pd.ExcelWriter(output_file, engine='openpyxl') as writer:
        combined_df.to_excel(writer, index=False, sheet_name='Combined')
        worksheet = writer.sheets['Combined']
        
        # Format Com No column as text and ensure empty strings
        for row in range(2, len(combined_df) + 2):
            cell = worksheet[f'A{row}']
            cell.number_format = '@'  # '@' is the text format in Excel
            com_no_val = combined_df.iloc[row-2]['Com No']
            # Set to empty string if missing
            if pd.isna(com_no_val) or str(com_no_val).strip() in ['', 'None', 'nan', 'NaN']:
                cell.value = ''
            else:
                cell.value = str(com_no_val)
    
    # Print summary
    print("\n" + "="*80)
    print("SUMMARY")
    print("="*80)
    print(f"\n✓ Processed {len(processed_sheets)} sheets:")
    for sheet in processed_sheets:
        print(f"  - {sheet}")
    
    print(f"\n✓ Total rows in combined file: {len(combined_df)}")
    print(f"✓ Columns: {list(combined_df.columns)}")
    
    # Location2 statistics
    loc2_count = sum(1 for x in combined_df['Location2'] if x != '')
    print(f"\n✓ Location2 values: {loc2_count}/{len(combined_df)} rows")
    
    # Breakdown by Location
    print(f"\n✓ Breakdown by Location:")
    location_counts = combined_df['Location'].value_counts()
    for loc, count in location_counts.items():
        print(f"  {loc}: {count} rows")
    
    # Unique Location2 values
    unique_loc2 = sorted([str(x) for x in combined_df[combined_df['Location2'] != '']['Location2'].unique() if x != ''])
    if unique_loc2:
        print(f"\n✓ Unique Location2 values ({len(unique_loc2)}):")
        for loc2 in unique_loc2:
            count = len(combined_df[combined_df['Location2'].astype(str) == loc2])
            print(f"  {loc2}: {count} rows")
    
    print(f"\n✓ File saved successfully: {output_file}")
    print("="*80)
    
    return True


def main():
    """Main function"""
    # Get script directory
    script_dir = os.path.dirname(os.path.abspath(__file__))
    
    # Default file paths
    input_file = os.path.join(script_dir, 'Setsco.xlsx')
    output_file = os.path.join(script_dir, 'Setsco_Combined.xlsx')
    
    # Allow command line arguments
    if len(sys.argv) > 1:
        input_file = sys.argv[1]
    if len(sys.argv) > 2:
        output_file = sys.argv[2]
    
    success = combine_setsco_sheets(input_file, output_file)
    
    if success:
        print("\n✓ Script completed successfully!")
        return 0
    else:
        print("\n✗ Script failed!")
        return 1


if __name__ == '__main__':
    sys.exit(main())

