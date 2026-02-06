/** @odoo-module **/

$(document).ready(function () {
  try {
      // Cache the jQuery selectors for better performance
      const $togglePassword = $("#b2b_toggle_password");
      const $toggleConfirmPassword = $("#b2b_toggle_confirm_password");
      const $passwordField = $("#password");
      const $confirmPasswordField = $("#confirm_password");

      // Toggle password visibility
      $togglePassword.on("click", function () {
          $(this).toggleClass("fa-eye fa-eye-slash");
          const type = $(this).hasClass("fa-eye") ? "text" : "password";
          $passwordField.attr("type", type);
      });

      // Toggle confirm password visibility
      $toggleConfirmPassword.on("click", function () {
          $(this).toggleClass("fa-eye fa-eye-slash");
          const type = $(this).hasClass("fa-eye") ? "text" : "password";
          $confirmPasswordField.attr("type", type);
      });
  } catch (error) {
      console.error('Error in password visibility toggle: ', error);
  }
});
