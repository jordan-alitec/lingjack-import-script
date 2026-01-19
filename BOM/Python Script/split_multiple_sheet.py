#!/usr/bin/env python3
import csv
import os
import argparse

def is_col_a_empty(row):
    # Column A = first column
    if not row:
        return True
    return str(row[0]).strip() == ""

def split_csv(input_csv, output_dir, batch_size=2000, has_header=True, encoding="utf-8-sig"):
    os.makedirs(output_dir, exist_ok=True)

    base = os.path.splitext(os.path.basename(input_csv))[0]

    with open(input_csv, "r", newline="", encoding=encoding) as f:
        reader = csv.reader(f)

        header = None
        if has_header:
            try:
                header = next(reader)
            except StopIteration:
                print("Input CSV is empty.")
                return

        file_index = 1
        current_rows = []
        total_written = 0

        def flush(rows, idx):
            nonlocal total_written
            out_path = os.path.join(output_dir, f"{base}_part_{idx:03d}.csv")
            with open(out_path, "w", newline="", encoding=encoding) as out:
                w = csv.writer(out)
                if header is not None:
                    w.writerow(header)
                w.writerows(rows)
            total_written += len(rows)
            print(f"Wrote {len(rows)} rows -> {out_path}")

        for row in reader:
            current_rows.append(row)

            # Once we hit >= batch_size, we may continue only if next rows have empty col A.
            if len(current_rows) >= batch_size:
                # Peek ahead by reading subsequent rows until we see a NON-empty Column A.
                # We can’t "peek" with csv.reader directly, so we manually pull rows and decide.
                while True:
                    # Try reading next row
                    try:
                        next_row = next(reader)
                    except StopIteration:
                        # No more rows; flush what we have and finish
                        flush(current_rows, file_index)
                        return

                    if is_col_a_empty(next_row):
                        # Rule: include it in the same file, keep going
                        current_rows.append(next_row)
                        continue
                    else:
                        # Found a non-empty Column A: end this file, start new file with that row
                        flush(current_rows, file_index)
                        file_index += 1
                        current_rows = [next_row]
                        break

        # Flush remaining rows
        if current_rows:
            flush(current_rows, file_index)

if __name__ == "__main__":
    ap = argparse.ArgumentParser(description="Split CSV into batches of 500 with Column A empty-row carryover rule.")
    ap.add_argument("input_csv", help="Path to input CSV")
    ap.add_argument("-o", "--output-dir", default="output_parts", help="Directory for output CSV files")
    ap.add_argument("-n", "--batch-size", type=int, default=500, help="Base batch size (default 500)")
    ap.add_argument("--no-header", action="store_true", help="Set if the CSV has NO header row")
    ap.add_argument("--encoding", default="utf-8-sig", help="File encoding (default utf-8-sig)")
    args = ap.parse_args()

    split_csv(
        input_csv= '',
        output_dir=args.output_dir,
        batch_size=args.batch_size,
        has_header=not args.no_header,
        encoding=args.encoding,
    )
