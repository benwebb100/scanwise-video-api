import os
from typing import Union, Literal
import argparse

class FileConverter:
    @staticmethod
    def to_hex(input_file: str, output_file: str = None, format: str = 'space') -> str:
        """
        Convert a file to hex format
        
        Args:
            input_file: Path to input file
            output_file: Path to output file (optional)
            format: Output format ('space', 'continuous', or 'formatted')
        
        Returns:
            Hex string if output_file is None
        """
        try:
            # Read binary file
            with open(input_file, 'rb') as f:
                binary_data = f.read()
            
            # Convert to hex
            if format == 'space':
                hex_string = ' '.join([f'{byte:02x}' for byte in binary_data])
            elif format == 'continuous':
                hex_string = ''.join([f'{byte:02x}' for byte in binary_data])
            elif format == 'formatted':
                # Format with 16 bytes per line
                hex_bytes = [f'{byte:02x}' for byte in binary_data]
                hex_string = '\n'.join(' '.join(hex_bytes[i:i+16]) 
                                     for i in range(0, len(hex_bytes), 16))
            else:
                raise ValueError("Format must be 'space', 'continuous', or 'formatted'")

            # Save to file if output path is provided
            if output_file:
                with open(output_file, 'w') as f:
                    f.write(hex_string)
                print(f"Converted file saved to: {output_file}")
                return output_file
            
            return hex_string

        except Exception as e:
            print(f"Error converting file: {str(e)}")
            return None

    @staticmethod
    def verify_hex_file(hex_file: str) -> bool:
        """Verify if a hex file is valid"""
        try:
            with open(hex_file, 'r') as f:
                hex_string = f.read().replace(" ", "").replace("\n", "")
            # Try converting hex to bytes
            bytes.fromhex(hex_string)
            return True
        except:
            return False

def convert_files():
    # Your specific file paths
    image_path = "C:\\Users\\aayush\\Downloads\\sample.jpg"
    audio_path = "C:\\Users\\aayush\\Downloads\\sample.mp3"
    
    # Create output paths in the same directory as the script
    script_dir = os.path.dirname(os.path.abspath(__file__))
    image_hex_path = os.path.join(script_dir, "image.hex")
    audio_hex_path = os.path.join(script_dir, "audio.hex")
    
    # Create converter instance
    converter = FileConverter()
    
    # Convert image
    print("\nConverting image...")
    image_result = converter.to_hex(image_path, image_hex_path, format='space')
    if image_result:
        print("Image conversion successful")
        if converter.verify_hex_file(image_hex_path):
            print("Image hex file verified")
    
    # Convert audio
    print("\nConverting audio...")
    audio_result = converter.to_hex(audio_path, audio_hex_path, format='space')
    if audio_result:
        print("Audio conversion successful")
        if converter.verify_hex_file(audio_hex_path):
            print("Audio hex file verified")
    
    return image_hex_path, audio_hex_path

if __name__ == "__main__":
    # If running with command line arguments
    if len(os.sys.argv) > 1:
        parser = argparse.ArgumentParser(description='Convert files to hex format')
        parser.add_argument('input_file', help='Input file path')
        parser.add_argument('-o', '--output', help='Output file path')
        parser.add_argument(
            '-f', '--format',
            choices=['space', 'continuous', 'formatted'],
            default='space',
            help='Output format (space-separated, continuous, or formatted)'
        )
        args = parser.parse_args()

        converter = FileConverter()
        result = converter.to_hex(args.input_file, args.output, args.format)
        
        if result and not args.output:
            print("\nHex output:")
            print(result)
    else:
        # Convert your specific files
        print("Converting specified files...")
        image_hex, audio_hex = convert_files()
        print(f"\nConverted files saved to:")
        print(f"Image hex: {image_hex}")
        print(f"Audio hex: {audio_hex}")