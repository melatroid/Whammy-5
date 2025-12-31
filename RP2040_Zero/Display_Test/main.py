from machine import Pin, I2C, SoftI2C
import time

def test_i2c():
    """I2C-Bus scan"""
    print("Scanning I2C bus...")
    
    try:
        i2c = I2C(1, scl=Pin(15), sda=Pin(14), freq=400000)
        devices = i2c.scan()
        print(f"I2C(0) found: {[hex(d) for d in devices]}")
        return i2c, devices
    except Exception as e:
        print(f"I2C(0) failed: {e}")
    
    
    return None, []

def main():
    print("\n=== SSD1315 Test on RP2040 Zero ===\n")
    
    # I2C testen
    i2c, devices = test_i2c()
    
    if not i2c:
        print("ERROR: No I2C communication possible!")
        print("\nCheck:")
        print("1. Wiring: SDA->GP0, SCL->GP1")
        print("2. Pull-up resistors: 4.7kΩ from SDA/SCL to 3.3V")
        print("3. Power: OLED VCC to 3.3V (NOT 5V!)")
        print("4. GND connection")
        return
    
    if not devices:
        print("ERROR: No I2C devices found!")
        print("Typical addresses for OLED: 0x3C or 0x3D")
        return
    
    addr = devices[0]
    print(f"\nUsing address: 0x{addr:02X}")
    
    try:
        from ssd1306 import SSD1306
        oled = SSD1306(128, 64, i2c, addr=addr)
        print("Display initialized!")
        
        oled.fill(0)
        oled.text("SSD1315 Test", 10, 0)
        oled.text(f"Addr: 0x{addr:02X}", 10, 16)
        oled.text("RP2040 Zero", 10, 32)
        oled.text("Success!", 10, 48)
        oled.show()
        
        time.sleep(2)
        for i in range(5):
            oled.fill(0)
            oled.text("MicroPython", 20, 20)
            oled.rect(10 + i*10, 40, 10, 10, 1, fill=True)
            oled.show()
            time.sleep(0.3)
        
        oled.fill(0)
        oled.text("OLED Working", 5, 5)
        oled.hline(5, 20, 118, 1)
        oled.text("Full contrast", 5, 30)
        oled.text("Test passed!", 5, 45)
        oled.show()
        
        print("\n=== Test completed successfully! ===")
        
    except Exception as e:
        print(f"\nERROR: {e}")
        print("\nTroubleshooting:")
        print("1. Try address 0x3C: oled = SSD1306(128, 64, i2c, 0x3C)")
        print("2. Try address 0x3D: oled = SSD1306(128, 64, i2c, 0x3D)")
        print("3. Lower I2C frequency: freq=100000")
        print("4. Check SSD1315 power (3.3V only!)")

if __name__ == "__main__":
    main()
