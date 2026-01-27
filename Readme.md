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
2. Select the hardware target (Board Target): for example `nrf54l15dk/nrf54l15/cpuapp` for our board.
3. Click on **Generate and build**.
4. Wait for the compilation to finish. If the message `Build completed successfully` appears in the terminal, the environment is functional.