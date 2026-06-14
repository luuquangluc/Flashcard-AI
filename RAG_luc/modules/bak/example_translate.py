import argostranslate.package
import argostranslate.translate

from_code = "en"
to_code = "vi"

# 1. Update package index
argostranslate.package.update_package_index()

# 2. Get available packages and find the English -> Vietnamese one
available_packages = argostranslate.package.get_available_packages()
package_to_install = next(
    filter(
        lambda x: x.from_code == from_code and x.to_code == to_code, available_packages
    )
)

# 3. Install the package
argostranslate.package.install_from_path(package_to_install.download())

# 4. Translate
text = "ielts" 
translated_text = argostranslate.translate.translate(text, from_code, to_code)

print(text, translated_text)