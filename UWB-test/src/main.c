#include <zephyr/kernel.h>
#include <zephyr/drivers/gpio.h>
#include <zephyr/sys/printk.h>

#define LED0_NODE DT_ALIAS(led1)

static const struct gpio_dt_spec led = GPIO_DT_SPEC_GET(LED0_NODE, gpios);

int main(void)
{
    int ret;

    // 1. Vérification Hardware
    if (!gpio_is_ready_dt(&led)) {
        return 0;
    }

    // 2. Configuration de la pin en sortie
    ret = gpio_pin_configure_dt(&led, GPIO_OUTPUT_ACTIVE);
    if (ret < 0) {
        return 0;
    }

    printk("Démarrage du test LED...\n");

    // 3. Boucle infinie
    while (1) {
        gpio_pin_toggle_dt(&led); // On inverse l'état (ON/OFF)
        printk("Blink !\n");      // Petit message dans le terminal pour être sûr
        k_msleep(1000);           // Pause de 1000ms (1 seconde)
    }
    return 0;
}