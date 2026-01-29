# nRF Connect Environment Configuration (nRF54L15)

This document describes the installation and compilation procedure for the Localization demonstrator project (UWB/BLE).

---

## 1. Tool Installation (Windows)

The recommended method uses the Nordic graphical manager to avoid path and dependency errors.

1. Download and install **nRF Connect for Desktop**.
2. Download and install **SEGGER J-Link** (latest version, required to flash Nordic boards).
3. Launch the application and install the **Toolchain Manager** module, which redirects to the VS Code extension.
4. In VS Code (method recommended by Nordic), install the extension: **nRF Connect for VS Code Extension Pack**.

> ⚠️ **Warning**: May conflict with other extensions such as *CMake Tools*. Disable these if necessary.

---

## 2. Creating and Configuring an Application

1. In the left sidebar (nRF icon), click on **Create a new application**.
2. Configure as follows:
   - *Create a blank application*
   - Select a **short path** to avoid compilation errors due to the path being too long.
   - Validate to create the project.

---

## 3. Compilation (Build)

Once the project is open:

1. In the **APPLICATIONS** panel (on the left), click on **+ Add build configuration**.
2. Select the hardware target (Board Target): for example `nrf52833dk/nrf52833` for our board.
3. Click on **Generate and build**.
4. Wait for the compilation to finish. If the message `Build completed successfully` appears in the terminal, the environment is functional.


## 4. Using DW3000 Examples (UWB)

To test localization with the **Decawave/Qorvo DW3000** module, we rely on the community driver for Zephyr.

### Driver Integration
1. Clone the examples repository:  
   `git clone https://github.com/br101/zephyr-dw3000-examples.git`
2. In VS Code, open the folder of a specific example (e.g., `examples/range_rx`).
3. Click the nRF icon and select **"Create an application"**, pointing to that directory.

### Hardware Configuration (Overlay)
The nRF54L15 communicates with the DW3000 via the **SPI** bus. You must ensure that the board's overlay file correctly defines the pins:
* **SCK / MOSI / MISO**: SPI Bus.
* **CS (Chip Select)**: Peripheral selection.
* **IRQ / RST**: Interrupt and reset signals for the UWB module.

---

## 4.1 Flashing and Debugging

Once the build configuration is generated (see Section 3):

1. **Connect the board**: Plug your nRF54L15 DK via USB.
2. **Flashing**: 
   - In the nRF Connect extension, under the **ACTIONS** tab, click **Flash**.
   - If multiple boards are connected, select the corresponding serial number.
3. **Reading Logs**:
   - Open the **Serial Terminal** (integrated into nRF Connect for Desktop or via VS Code).
   - Select the COM port of the board.
   - Settings: **115200 baud**.

---

## 4.2 Troubleshooting

| Issue | Solution |
| :--- | :--- |
| **Compilation Error (Path too long)** | Move the project to the disk root (e.g., `C:\nrf\`). |
| **DW3000 not initialized** | Check SPI wiring and the 3.3V power supply to the module. |
| **Device not detected** | Ensure SEGGER J-Link is up to date and the board power switch is "ON". |
