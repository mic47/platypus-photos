// https://docs.expo.dev/guides/using-eslint/
// This file exists because otherwise expo want to install it. But then it uses eslint.config.js instead, even from other directories...
module.exports = {
        extends: ['expo', "eslint:recommended"],
        ignorePatterns: [
                "scripts/reset-project.js"
        ]
};
